# TradingPlatform UI Milestone 2

## Shell Productivity

This cumulative UI release builds on UI Milestone 1 and adds keyboard navigation, a global command palette, favorites, recent workspaces, and persisted workstation preferences without changing backend APIs or page workflows.

## Primary controls

- `Command+K` on macOS or `Ctrl+K` elsewhere: open the command palette.
- `Option+R` / `Alt+R`: refresh global context.
- `Option+B` / `Alt+B`: collapse or expand navigation.
- `Option+,` / `Alt+,`: open workstation preferences.
- Star button in the global header: favorite the active workspace.

## Apply

```bash
./APPLY_UI_MILESTONE2_SHELL_PRODUCTIVITY.sh /Users/vinay.hatti/TradingPlatform
```

## Validate

```bash
cd /Users/vinay.hatti/TradingPlatform/ui/workstation
npm test
npm run typecheck
npm run build
```

## Rollback

```bash
./ROLLBACK_UI_MILESTONE2_SHELL_PRODUCTIVITY.sh /Users/vinay.hatti/TradingPlatform
```
