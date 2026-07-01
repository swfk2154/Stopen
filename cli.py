#!/usr/bin/env python3
"""Stopen CLI — 交互式渗透测试终端

用法:
    python cli.py                    # 交互式 REPL 模式
    python cli.py run <target>       # 一键渗透
    python cli.py recon <target>     # 信息收集
    python cli.py scan <target>      # 漏洞扫描
    python cli.py status             # 系统状态
    python cli.py --port 8081        # 指定后端端口
"""
import argparse
import json
import os
import sys
import httpx

# ── ANSI 颜色 ──
class C:
    PURPLE = '\033[95m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    DIM = '\033[2m'
    BOLD = '\033[1m'
    RESET = '\033[0m'

def p(text="", **kw):
    print(text, **kw)

def pp(text, color=""):
    """打印带颜色的文本"""
    if color and sys.stdout.isatty():
        print(f"{color}{text}{C.RESET}")
    else:
        print(text)

def header(text):
    pp(f"\n{C.BOLD}{C.PURPLE}═══ {text} ═══{C.RESET}")

def ok(text):
    pp(f"  {C.GREEN}✓{C.RESET} {text}")

def fail(text):
    pp(f"  {C.RED}✗{C.RESET} {text}")

def info(text):
    pp(f"  {C.DIM}{text}{C.RESET}")

def dim(text):
    pp(f"{C.DIM}{text}{C.RESET}")

SEP = "─" * 56

# Logo (ANSI safe)
LOGO = f"""{C.PURPLE}{C.BOLD}
  ███████  ████████  ██████   ██████  ███████ ███    ██
  ██         ██    ██    ██ ██    ██ ██      ████   ██
  ███████    ██    ██    ██ ██    ██ █████   ██ ██  ██
       ██    ██    ██    ██ ██    ██ ██      ██  ██ ██
  ███████    ██     ██████   ██████  ███████ ██   ████{C.RESET}
  {C.DIM}自动化渗透测试 Agent  v1.0{C.RESET}"""


# ── 工具函数 ──

def _sv(s: str) -> str:
    """status 转可视符号"""
    m = {"running": f"{C.GREEN}● 运行中{C.RESET}", "stopped": f"{C.DIM}● 已停止{C.RESET}",
         "active": f"{C.GREEN}● 活跃{C.RESET}", "dead": f"{C.RED}● 离线{C.RESET}",
         "connected": f"{C.GREEN}● 已连接{C.RESET}", "disconnected": f"{C.RED}● 未连接{C.RESET}",
         "completed": f"{C.GREEN}已完成{C.RESET}", "failed": f"{C.RED}失败{C.RESET}",
         "pending": f"{C.YELLOW}等待中{C.RESET}"}
    return m.get(s, s)

def _sev(s: str) -> str:
    cs = {"critical": C.RED, "high": C.YELLOW, "medium": C.YELLOW, "low": C.BLUE, "info": C.DIM}
    return f"{cs.get(s, '')}{s.upper()}{C.RESET}"


# ── 核心 CLI ──

class StopenCLI:
    def __init__(self, api_base: str):
        self.api_base = api_base
        self.target = ""
        self.goal = ""
        try:
            self._http = httpx.Client(base_url=api_base, timeout=60)
        except Exception:
            self._http = None

    # ── API ──

    def _api(self, method: str, path: str, **kw):
        if not self._http:
            fail(f"后端未连接: {self.api_base}")
            return None
        try:
            r = self._http.request(method, path, **kw)
            return r.json()
        except httpx.ConnectError:
            fail(f"无法连接后端: {self.api_base}\n  请先启动: python run.py --port {self.api_base.split(':')[-1]}")
            return None
        except Exception as e:
            fail(f"请求失败: {e}")
            return None

    def _stream(self, method: str, path: str, **kw):
        if not self._http:
            return
        try:
            with self._http.stream(method, path, **kw) as r:
                # 检查 HTTP 状态码
                if r.status_code != 200:
                    yield f"\n[ERROR] 后端返回 HTTP {r.status_code}\n"
                    try:
                        body = r.read().decode('utf-8', errors='replace')[:200]
                        yield f"[ERROR] {body}\n"
                    except Exception:
                        pass
                    return
                for line in r.iter_lines():
                    if not line:
                        continue
                    if line.startswith("data: "):
                        data = line[6:]
                        if data == "[DONE]":
                            break
                        try:
                            token = json.loads(data).get("token", "")
                            if not token:
                                continue  # 跳过空 token
                            yield token
                        except json.JSONDecodeError:
                            yield data
        except httpx.ConnectError:
            yield f"\n[ERROR] 无法连接后端: {self.api_base}\n"

    # ── 命令 ──

    def do_target(self, args):
        if not args:
            pp(f"  当前目标: {C.CYAN}{self.target or '(未设置)'}{C.RESET}")
            return
        self.target = args[0]
        ok(f"目标已设置: {C.BOLD}{C.CYAN}{self.target}{C.RESET}")

    def do_goal(self, args):
        self.goal = " ".join(args)
        ok(f"目标说明: {self.goal}")

    def do_run(self, args):
        t = args[0] if args else self.target
        if not t:
            fail("请先设置目标: target <host>")
            return
        self.target = t
        header(f"全自动渗透: {t}")
        for token in self._stream("POST", "/api/agent/run", json={"target": t, "goal": self.goal, "task_type": "pentest"}):
            print(token, end="", flush=True)
        print()

    def do_recon(self, args):
        t = args[0] if args else self.target
        if not t:
            fail("请先设置目标")
            return
        self.target = t
        header(f"信息收集: {t}")
        for token in self._stream("POST", "/api/agent/run", json={"target": t, "goal": "信息收集", "task_type": "pentest"}):
            print(token, end="", flush=True)
        print()

    def do_scan(self, args):
        t = args[0] if args else self.target
        if not t:
            fail("请先设置目标")
            return
        header(f"漏洞扫描: {t}")
        for token in self._stream("POST", "/api/agent/run", json={"target": t, "goal": "漏洞扫描", "task_type": "pentest"}):
            print(token, end="", flush=True)
        print()

    def do_exploit(self, args):
        t = args[0] if args else self.target
        if not t:
            fail("请先设置目标")
            return
        header(f"漏洞利用: {t}")
        for token in self._stream("POST", "/api/agent/run", json={"target": t, "goal": "漏洞利用", "task_type": "pentest"}):
            print(token, end="", flush=True)
        print()

    def do_tools(self, _args):
        data = self._api("GET", "/api/tools")
        if not data:
            return
        tools = data.get("tools", [])
        mcp = data.get("mcp_servers", {})
        header(f"已注册工具 ({data.get('count', 0)})")
        if tools:
            print(f"  {'工具名':<20} {'分类':<12} {'描述'}")
            print(f"  {'─'*20} {'─'*12} {'─'*30}")
            for t in tools:
                print(f"  {C.CYAN}{t['name']:<20}{C.RESET} {t['category']:<12} {t['description'][:50]}")
        if mcp:
            print()
            header("MCP 服务器")
            for name, st in mcp.items():
                print(f"  {name}: {_sv(st)}")

    def do_status(self, _args):
        health = self._api("GET", "/api/health")
        if not health:
            return
        tools_data = self._api("GET", "/api/tools")
        header("系统状态")
        print(f"  目标    {C.CYAN}{self.target or '(未设置)'}{C.RESET}")
        print(f"  后端    {C.GREEN}{health.get('status', '?')}{C.RESET}  v{health.get('version', '?')}")
        print(f"  功能    {C.DIM}{', '.join(health.get('features', []))}{C.RESET}")
        if tools_data:
            print(f"  工具    {tools_data.get('count', 0)} 个已注册")
            for cat, names in _group_tools(tools_data.get("tools", [])).items():
                print(f"          {C.DIM}{cat}: {', '.join(names)}{C.RESET}")
            for name, st in (tools_data.get("mcp_servers", {})).items():
                print(f"  MCP     {name}: {_sv(st)}")

    def do_listeners(self, _args):
        data = self._api("GET", "/api/c2/listeners")
        if not data:
            return
        ls = data.get("listeners", [])
        if not ls:
            info("暂无监听器")
            return
        header(f"C2 监听器 ({len(ls)})")
        for l in ls:
            enc = l.get("encryption_type", "aes")
            print(f"  {_sv(l['status'])} {C.CYAN}{l['name']}{C.RESET} ({l['listener_type']}) {l['host']}:{l['port']} [{enc}]")

    def do_sessions(self, _args):
        data = self._api("GET", "/api/c2/sessions")
        if not data:
            return
        ss = data.get("sessions", [])
        if not ss:
            info("暂无活跃会话")
            return
        header(f"C2 会话 ({len(ss)})")
        for s in ss:
            print(f"  {_sv(s['status'])} {C.CYAN}{s['remote_addr']}{C.RESET} | {s.get('hostname', '?')} | {s.get('username', '?')}")

    def do_webshells(self, _args):
        data = self._api("GET", "/api/webshell")
        if not data:
            return
        ws = data.get("webshells", [])
        if not ws:
            info("暂无 WebShell")
            return
        header(f"WebShell ({len(ws)})")
        for w in ws:
            print(f"  {C.CYAN}{w['name']}{C.RESET} ({w.get('shell_type', '?')}) [{w.get('protocol', 'antsword')}] {w['url']}")

    def do_vulns(self, _args):
        stats = self._api("GET", "/api/vulnerabilities/stats")
        data = self._api("GET", "/api/vulnerabilities")
        if not data:
            return
        vulns = data.get("vulnerabilities", [])
        if not vulns:
            info("暂无漏洞")
            return
        if stats:
            parts = [f"{_sev(k)} {v}" for k, v in sorted(stats.get("by_severity", {}).items())]
            print(f"\n  漏洞统计: 总数 {C.BOLD}{stats.get('total', 0)}{C.RESET}  |  {' | '.join(parts)}")
        header(f"漏洞列表 ({len(vulns)})")
        for v in vulns:
            print(f"  {_sev(v['severity'])} {v['title'][:50]}  {C.DIM}{v.get('target', '')[:25]} [{v['status']}]{C.RESET}")

    def do_config(self, args):
        if args and args[0] == "providers":
            data = self._api("GET", "/api/config/providers")
            if not data:
                return
            header("LLM 提供商")
            for p in data.get("providers", []):
                key_st = f"{C.GREEN}已配置{C.RESET}" if p.get("has_key") else f"{C.RED}未配置{C.RESET}"
                en_st = f"{C.GREEN}✓{C.RESET}" if p.get("enabled") else f"{C.DIM}✗{C.RESET}"
                models = ", ".join(p.get("models", [])[:3])
                print(f"  {en_st} {p['name']:<12} Key: {key_st}  [{models}]")
        else:
            info("用法: config providers")

    def do_health(self, _args):
        try:
            r = self._http.get("/api/health")
            if r.status_code == 200:
                d = r.json()
                ok(f"后端连接正常 (v{d.get('version', '?')})")
            else:
                fail(f"后端返回 HTTP {r.status_code}")
        except Exception as e:
            fail(f"连接失败: {e}")

    def do_help(self, _args):
        self._show_help()

    def do_exit(self, _args):
        pp(f"\n{C.DIM}👋 再见{C.RESET}")
        if self._http:
            self._http.close()
        sys.exit(0)

    # ── 自然语言对话 ──

    def _do_chat(self, text: str):
        """自然语言对话，走 LLM 聊天接口"""
        # 获取或创建对话
        data = self._api("GET", "/api/chat/conversations")
        convs = data.get("conversations", []) if data else []
        active_cid = convs[0]["id"] if convs else None

        if not active_cid:
            r = self._api("POST", "/api/chat/conversations", json={"title": "CLI 对话"})
            if r:
                active_cid = r.get("id", "")
            else:
                fail("创建对话失败")
                return

        # 发送消息并等待回复
        pp(f"\n{C.CYAN}[对话]{C.RESET} {text}\n")
        try:
            resp = self._http.post(
                f"{self.api_base}/api/chat/conversations/{active_cid}/messages",
                json={"content": text, "role": "user", "use_agent": True},
                timeout=60,
            )
            data = resp.json()
            assistant = data.get("assistant", "")
            if assistant:
                pp(f"{C.GREEN}[AI]{C.RESET} {assistant}")
            elif data.get("error"):
                fail(f"AI 回复失败: {data['error']}")
            else:
                fail(f"AI 无回复 ({resp.status_code})")
        except httpx.TimeoutException:
            fail("请求超时，AI 思考太久")
        except Exception as e:
            fail(f"对话失败: {e}")

    # ── 帮助 ──

    def _show_help(self):
        header("命令帮助")
        cmds = [
            ("target", "<host>", "设置渗透目标"),
            ("goal", "<描述>", "设置目标说明"),
            ("run", "[目标]", "全自动渗透测试"),
            ("recon", "[目标]", "信息收集"),
            ("scan", "[目标]", "漏洞扫描"),
            ("exploit", "[目标]", "漏洞利用"),
            ("tools", "", "列出所有可用工具"),
            ("status", "", "查看系统状态"),
            ("listeners", "", "C2 监听器列表"),
            ("sessions", "", "活跃 C2 会话"),
            ("webshells", "", "WebShell 列表"),
            ("vulns", "", "漏洞列表"),
            ("config providers", "", "查看 LLM 配置"),
            ("health", "", "检查后端连接"),
            ("exit / q", "", "退出"),
        ]
        print(f"  {'命令':<20} {'参数':<18} {'说明'}")
        print(f"  {'─'*20} {'─'*18} {'─'*30}")
        for cmd, params, desc in cmds:
            print(f"  {C.CYAN}{cmd:<20}{C.RESET} {C.DIM}{params:<18}{C.RESET} {desc}")

    # ── 主循环 ──

    def run(self):
        health = self._api("GET", "/api/health")
        if health is None:
            return

        os.system("cls" if os.name == "nt" else "clear")
        print(LOGO)
        print(SEP)
        features = ", ".join(health.get("features", []))
        print(f"  后端: {self.api_base}  版本: {health.get('version', '?')}")
        print(f"  功能: {features}")
        print(SEP)
        dim("  输入 help 查看命令  |  exit 退出")
        print()

        while True:
            try:
                raw = input(f"{C.PURPLE}Stopen>{C.RESET} ").strip()
            except (EOFError, KeyboardInterrupt):
                self.do_exit([])
                break
            if not raw:
                continue

            parts = raw.split()
            cmd = parts[0].lower()
            args = parts[1:]

            handlers = {
                "target": self.do_target, "goal": self.do_goal,
                "run": self.do_run, "recon": self.do_recon,
                "scan": self.do_scan, "exploit": self.do_exploit,
                "tools": self.do_tools, "status": self.do_status,
                "listeners": self.do_listeners, "sessions": self.do_sessions,
                "webshells": self.do_webshells, "vulns": self.do_vulns,
                "config": self.do_config, "health": self.do_health,
                "help": self.do_help,
                "exit": self.do_exit, "quit": self.do_exit, "q": self.do_exit,
            }
            h = handlers.get(cmd)
            if h:
                h(args)
            else:
                # 未知命令 → 自然语言对话，发给 Agent 执行
                self._do_chat(raw)


def _group_tools(tools):
    cats = {}
    for t in tools:
        cats.setdefault(t["category"], []).append(t["name"])
    return cats


# ── 入口 ──

def main():
    parser = argparse.ArgumentParser(description="Stopen CLI — 渗透测试终端")
    parser.add_argument("command", nargs="?", help="run / recon / scan / exploit / status / tools / health")
    parser.add_argument("target", nargs="?", help="目标 IP/域名/URL")
    parser.add_argument("--port", type=int, default=int(os.environ.get("STOPEN_PORT", 8080)), help="后端端口 (默认 8080)")
    args = parser.parse_args()

    cli = StopenCLI(f"http://127.0.0.1:{args.port}")

    if args.command:
        h = {
            "run": cli.do_run, "recon": cli.do_recon, "scan": cli.do_scan,
            "exploit": cli.do_exploit, "status": cli.do_status,
            "tools": cli.do_tools, "health": cli.do_health,
            "listeners": cli.do_listeners, "sessions": cli.do_sessions,
            "webshells": cli.do_webshells, "vulns": cli.do_vulns,
        }
        handler = h.get(args.command)
        if handler:
            handler([args.target] if args.target else [])
        else:
            fail(f"未知命令: {args.command}")
    else:
        cli.run()


if __name__ == "__main__":
    main()
