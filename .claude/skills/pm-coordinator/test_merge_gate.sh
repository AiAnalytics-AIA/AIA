#!/bin/bash
# The gate against a mocked gh: a failed check-runs read must never reach the merge endpoint, and a PR that
# passes every check must, with Codex's state comment on the second page of comments.
# Run: bash .claude/skills/pm-coordinator/test_merge_gate.sh
here=$(cd "$(dirname "$0")" && pwd); tmp=$(mktemp -d); trap 'rm -rf "$tmp"' EXIT
export SHA=0123456789abcdef0123456789abcdef01234567 MOCK_DIR="$tmp" PM_STATE="$tmp/state"
mkdir -p "$tmp/bin" "$PM_STATE"
# The mock answers what each call's --jq would print, and the paginated comments and reviews as raw pages;
# check-runs fails with no output when MOCK_CHECKS=fail.
cat > "$tmp/bin/gh" <<'EOF'
#!/bin/bash
case "$*" in
  *"-X PUT"*/merge*) touch "$MOCK_DIR/merged"; echo "mergesha true";;
  *check-runs*) [ "$MOCK_CHECKS" = fail ] && exit 1
    echo '["success","success","success","success","success","success","success","success","success","success","success","skipped"]';;
  *ccr/review_threads*) echo 0;;
  *issues/*/comments*) echo '[{"user":{"login":"someone"},"body":"page one"}]'   # Codex's state only on page two
    [[ "$*" == *--paginate* ]] && jq -nc --arg b "<!-- codex-review-state:v1 {\"code_review\":{\"commit_sha\":\"$SHA\",\"has_any_findings\":false,\"has_unresolved_findings\":false,\"status\":\"completed\"}} -->" '[{user:{login:"chatgpt-codex-connector[bot]"},body:$b}]';;
  */reviews*) echo '[]';;
  *pulls/*) echo "{\"mergeable_state\":\"clean\",\"draft\":false,\"head\":{\"sha\":\"$SHA\"},\"base\":{\"ref\":\"develop\"}}";;
  *) exit 1;;
esac
EOF
chmod +x "$tmp/bin/gh"; export PATH="$tmp/bin:$PATH"; fail=0

echo "7:${SHA:0:8}" > "$PM_STATE/pins.txt"; rm -f "$tmp/merged"
out=$(MOCK_CHECKS=fail bash "$here/merge_gate.sh" 7 2>&1); code=$?
if [ $code -ne 0 ] && [ ! -e "$tmp/merged" ] && grep -q "^7:" "$PM_STATE/pins.txt"; then echo "ok    a failed check-runs read refuses: $out"
else echo "FAIL  a failed check-runs read reached the merge (exit $code): $out"; fail=1; fi

echo "7:${SHA:0:8}" > "$PM_STATE/pins.txt"; rm -f "$tmp/merged"
out=$(bash "$here/merge_gate.sh" 7 2>&1); code=$?
if [ $code -eq 0 ] && [ -e "$tmp/merged" ] && ! grep -q "^7:" "$PM_STATE/pins.txt"; then echo "ok    a PR that passes every check merges, Codex's state read from page two: $out"
else echo "FAIL  a passing PR did not merge (exit $code): $out"; fail=1; fi
exit $fail
