# Command cheatsheet

## Daemon/provider

```bash
paseo status
paseo provider ls
paseo provider models <provider>
paseo --version
```

## Agent

```bash
paseo ls --all --global
paseo inspect <id> --json
paseo logs <id>
paseo send <id> "<follow-up>"
paseo stop <id>
paseo archive <id>
```

## Workspace/script

```bash
paseo workspace --help
paseo script ls --cwd <path>
paseo script start <name> --cwd <path>
paseo script stop <name> --cwd <path>
```

## Health/debug

```bash
curl -sS http://127.0.0.1:6767/api/health
tail -n 200 ~/.paseo/daemon.log
rg -n "provider|agent|permission|error" ~/.paseo/daemon.log
```

## Role/runtime

```bash
~/.local/bin/codex-room-sync supervisor
rg -n "model_catalog_json|multi_agent_version" ~/.codex-runtime/supervisor
find ~/.codex-runtime -maxdepth 2 -type f -print
```

Không chạy launcher trực tiếp để debug nếu không cần; nó sẽ exec một Codex process. Ưu tiên `paseo inspect`/`provider models` trước.
