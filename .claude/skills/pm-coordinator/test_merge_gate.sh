#!/bin/bash
# The gate against a mocked gh: every read that fails or is incomplete refuses and never reaches the merge
# endpoint, and only a clean stand-in review replaces Codex. Run: bash .claude/skills/pm-coordinator/test_merge_gate.sh
here=$(cd "$(dirname "$0")" && pwd); tmp=$(mktemp -d); trap 'rm -rf "$tmp"' EXIT
export SHA=0123456789abcdef0123456789abcdef01234567 MOCK_DIR="$tmp" PM_STATE="$tmp/state"
mkdir -p "$tmp/bin" "$PM_STATE"
# The mock answers what each --jq call would print, and the paginated comments and reviews as raw pages.
# MOCK_CHECKS=fail: check-runs fails with no output. Comments: page one has no Codex state, page two Codex's
# completed state on the head (MOCK_CODEX=none: no page two); MOCK_COMMENTS=partial: a later page fails.
# MOCK_REVIEW: the stand-in reviews on the head (clean, changes, findings, stale); MOCK_REVIEWS=partial: a
# later page fails after a clean one.
cat > "$tmp/bin/gh" <<'EOF'
#!/bin/bash
review() { jq -nc --arg s "$SHA" --arg st "$1" --arg at "$2" --arg b "$3" \
  '{commit_id:$s,state:$st,submitted_at:$at,body:("[Claude review, Codex stand-in] on the head\n"+$b)}'; }
case "$*" in
  *"-X PUT"*/merge*) touch "$MOCK_DIR/merged"; echo "mergesha true";;
  *check-runs*) [ "$MOCK_CHECKS" = fail ] && exit 1
    echo '["success","success","success","success","success","success","success","success","success","success","success","skipped"]';;
  *ccr/review_threads*) echo 0;;
  *issues/*/comments*) echo '[{"user":{"login":"someone"},"body":"page one"}]'
    [ "$MOCK_CODEX" = none ] && exit 0
    [[ "$*" == *--paginate* ]] && jq -nc --arg b "<!-- codex-review-state:v1 {\"code_review\":{\"commit_sha\":\"$SHA\",\"has_any_findings\":false,\"has_unresolved_findings\":false,\"status\":\"completed\"}} -->" '[{user:{login:"chatgpt-codex-connector[bot]"},body:$b}]'
    [ "$MOCK_COMMENTS" = partial ] && exit 1; exit 0;;
  */reviews*) case "$MOCK_REVIEW" in
      clean) echo "[$(review COMMENTED 2026-10-27T10:00:00Z 'Verdict: clean')]";;
      changes) echo "[$(review CHANGES_REQUESTED 2026-10-27T10:00:00Z 'Verdict: clean')]";;
      findings) echo "[$(review COMMENTED 2026-10-27T10:00:00Z 'Verdict: findings (one P1 open)')]";;
      stale) echo "[$(review COMMENTED 2026-10-27T10:00:00Z 'Verdict: clean'),$(review COMMENTED 2026-10-27T11:00:00Z 'Verdict: findings')]";;
      *) echo '[]';;
    esac
    [ "$MOCK_REVIEWS" = partial ] && exit 1; exit 0;;
  *pulls/*) echo "{\"mergeable_state\":\"clean\",\"draft\":false,\"head\":{\"sha\":\"$SHA\"},\"base\":{\"ref\":\"develop\"}}";;
  *) exit 1;;
esac
EOF
chmod +x "$tmp/bin/gh"; export PATH="$tmp/bin:$PATH"; fail=0

check() {  # check merge|refuse <name> [VAR=value ...]
  local want=$1 name=$2; shift 2
  echo "7:${SHA:0:8}" > "$PM_STATE/pins.txt"; rm -f "$tmp/merged"
  out=$(env "$@" bash "$here/merge_gate.sh" 7 2>&1); code=$?
  if [ "$want" = merge ]; then [ $code -eq 0 ] && [ -e "$tmp/merged" ] && ! grep -q "^7:" "$PM_STATE/pins.txt"
  else [ $code -ne 0 ] && [ ! -e "$tmp/merged" ] && grep -q "^7:" "$PM_STATE/pins.txt"; fi
  if [ $? -eq 0 ]; then echo "ok    $name: $out"; else echo "FAIL  $name (exit $code): $out"; fail=1; fi
}
check refuse "a failed check-runs read refuses" MOCK_CHECKS=fail
check merge "Codex completed on the head, its state read from page two"
check refuse "a comments read failing on a later page refuses" MOCK_COMMENTS=partial
check merge "no Codex state, a clean stand-in review merges" MOCK_CODEX=none MOCK_REVIEW=clean
check refuse "a stand-in review requesting changes refuses" MOCK_CODEX=none MOCK_REVIEW=changes
check refuse "a stand-in review with findings refuses" MOCK_CODEX=none MOCK_REVIEW=findings
check refuse "a newer stand-in review with findings outranks an older clean one" MOCK_CODEX=none MOCK_REVIEW=stale
check refuse "a reviews read failing on a later page refuses" MOCK_CODEX=none MOCK_REVIEW=clean MOCK_REVIEWS=partial
check refuse "no Codex state and no stand-in review refuses" MOCK_CODEX=none
exit $fail
