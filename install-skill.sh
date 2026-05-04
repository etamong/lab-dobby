#!/usr/bin/env bash
# Claude Code skill을 글로벌 ~/.claude/skills/ 로 설치합니다.
# 사용: bash install-skill.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC="$SCRIPT_DIR/.claude/skills/setup-labdobby"
DEST="$HOME/.claude/skills"

if [ ! -d "$SRC" ]; then
  echo "skill 소스를 못 찾았어요: $SRC" >&2
  exit 1
fi

mkdir -p "$DEST"
cp -R "$SRC" "$DEST/"
echo "✅ skill 설치됨: $DEST/setup-labdobby"
echo
echo "이제 Claude Code에서 /setup-labdobby 라고 치면 셋업 가이드가 시작돼요."
