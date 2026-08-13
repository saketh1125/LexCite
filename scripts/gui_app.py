import json
import subprocess
import threading
import tkinter as tk
from tkinter import messagebox, scrolledtext

BASE_URL_DEFAULT = "http://127.0.0.1:8000"


class LexCiteGUI:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        root.title("LexCite — grounded Q&A over a legal corpus")
        root.geometry("980x680")
        root.resizable(True, True)

        top = tk.Frame(root, padx=12, pady=10)
        top.pack(fill="x")
        tk.Label(top, text="Server base URL:").pack(side="left")
        self.base_var = tk.StringVar(value=BASE_URL_DEFAULT)
        tk.Entry(top, textvariable=self.base_var, width=40).pack(side="left", padx=8)

        self.health_btn = tk.Button(top, text="Health", command=self.on_health)
        self.health_btn.pack(side="left", padx=4)
        self.ingest_btn = tk.Button(top, text="Ingest", command=self.on_ingest)
        self.ingest_btn.pack(side="left", padx=4)

        ask = tk.Frame(root, padx=12, pady=6)
        ask.pack(fill="x")
        tk.Label(ask, text="Question:").pack(side="left")
        self.question_var = tk.StringVar()
        tk.Entry(ask, textvariable=self.question_var).pack(side="left", fill="x", expand=True, padx=8)
        self.ask_btn = tk.Button(ask, text="Ask", command=self.on_ask)
        self.ask_btn.pack(side="left")

        out = tk.Frame(root, padx=12, pady=6)
        out.pack(fill="both", expand=True)
        self.output = scrolledtext.ScrolledText(out, wrap="word", font=("Monospace", 10), state="disabled")
        self.output.pack(fill="both", expand=True)

        self.status_var = tk.StringVar(value="ready")
        tk.Label(root, textvariable=self.status_var, anchor="w", padx=12, pady=4).pack(fill="x")

    # ---- UI helpers -------------------------------------------------------

    def _base(self) -> str:
        base = self.base_var.get().strip().rstrip("/")
        if not base:
            messagebox.showwarning("LexCite", "Server base URL is empty")
        return base

    def _append(self, text: str) -> None:
        self.output.configure(state="normal")
        self.output.insert("end", text)
        self.output.see("end")
        self.output.configure(state="disabled")

    def _clear(self) -> None:
        self.output.configure(state="normal")
        self.output.delete("1.0", "end")
        self.output.configure(state="disabled")

    def _run(self, command: list[str], label: str) -> None:
        self._set_busy(True)
        header = f"$ {subprocess.list2cmdline(command)}\n"
        self._append(header + "-" * len(header) + "\n")

        def worker():
            try:
                proc = subprocess.run(command, capture_output=True, text=True, timeout=600)
                body = proc.stdout.strip() or proc.stderr.strip()
                if body:
                    try:
                        body = json.dumps(json.loads(body), indent=2, ensure_ascii=False)
                    except ValueError:
                        pass
                    self.root.after(0, self._append, body + "\n\n")
                else:
                    self.root.after(0, self._append, "(empty response)\n\n")
                if proc.returncode != 0:
                    self.root.after(0, self._append, f"curl exit code {proc.returncode}\n\n")
            except subprocess.TimeoutExpired:
                self.root.after(0, self._append, "request timed out (10 min)\n\n")
            except Exception as exc:
                self.root.after(0, self._append, f"error: {exc}\n\n")
            finally:
                self.root.after(0, lambda: (self._set_busy(False), self._set_status("done")))

        threading.Thread(target=worker, daemon=True).start()
        self._set_status(f"running: {label} ...")

    def _set_busy(self, busy: bool) -> None:
        state = "disabled" if busy else "normal"
        for btn in (self.health_btn, self.ingest_btn, self.ask_btn):
            btn.configure(state=state)

    def _set_status(self, text: str) -> None:
        self.status_var.set(text)

    # ---- actions ----------------------------------------------------------

    def on_health(self) -> None:
        base = self._base()
        if base:
            self._clear()
            self._run(["curl", "-s", f"{base}/health"], "health")

    def on_ingest(self) -> None:
        base = self._base()
        if base:
            self._clear()
            self._run(["curl", "-s", "-X", "POST", f"{base}/ingest"], "ingest")

    def on_ask(self) -> None:
        base = self._base()
        question = self.question_var.get().strip()
        if not base:
            return
        if not question:
            messagebox.showwarning("LexCite", "Type a question first")
            return
        self._clear()
        payload = json.dumps({"question": question}, ensure_ascii=False)
        self._run(
            ["curl", "-s", f"{base}/ask", "-H", "Content-Type: application/json", "-d", payload],
            "ask",
        )


def main() -> None:
    root = tk.Tk()
    LexCiteGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()