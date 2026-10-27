#!/bin/bash
# merge PR $1 if head==pin, all checks done & no failure, clean, 0 unresolved threads, Codex done on head
# State lives in $PM_STATE (default ./pm-state), outside the repo: pins.txt (PR:sha8), docsonly.txt (PR),
# after.txt (PR:PR, merge order), codex-stuck.txt (PR); each merge is appended to merged.log.
cd "${PM_STATE:-./pm-state}" || exit 1
pr=$1; want=$(grep "^$pr:" pins.txt | cut -d: -f2)
for dep in $(grep "^$pr:" after.txt 2>/dev/null | cut -d: -f2); do
  [ "$(gh api repos/aianalytics-aia/aia/pulls/$dep --jq .merged)" = true ] || { echo "#$pr waits for #$dep (merge order)"; exit 1; }
done
[ -z "$want" ] && { echo "#$pr not pinned"; exit 1; }
for i in $(seq 1 10); do j=$(gh api repos/aianalytics-aia/aia/pulls/$pr); st=$(jq -r .mergeable_state <<<"$j"); [ "$st" != unknown ] && break; sleep 5; done
sha=$(jq -r .head.sha <<<"$j"); dr=$(jq -r .draft <<<"$j")
[ "${sha:0:8}" != "$want" ] && { echo "#$pr head ${sha:0:8} != $want"; exit 1; }
[ "$dr" = true ] && { echo "#$pr draft"; exit 1; }
base=$(jq -r .base.ref <<<"$j"); [ "$base" != develop ] && { echo "#$pr base $base (stacked; waits for retarget)"; exit 1; }
[ "$st" != clean ] && { echo "#$pr state $st"; exit 1; }
cr=$(gh api --paginate "repos/aianalytics-aia/aia/commits/$sha/check-runs?per_page=100") || { echo "#$pr check runs unreadable"; exit 1; }
r=$(jq -cs '[.[].check_runs[]|(.conclusion//.status)]' <<<"$cr")
bad=$(jq '[.[]|select(.!="success" and .!="skipped")]|length' <<<"$r"); n=$(jq length <<<"$r")
[[ "$bad" =~ ^[0-9]+$ && "$n" =~ ^[0-9]+$ ]] || { echo "#$pr check runs unreadable: $r"; exit 1; }
min=12; grep -qx "$pr" docsonly.txt 2>/dev/null && min=1
[ "$bad" != 0 -o "$n" -lt $min ] && { echo "#$pr checks $r"; exit 1; }
t=$(gh api repos/aianalytics-aia/aia/pulls/$pr/ccr/review_threads --jq '[.[]?|select(.resolved==false)]|length')
[ "$t" != 0 ] && { echo "#$pr $t open threads"; exit 1; }
cj=$(gh api --paginate "repos/aianalytics-aia/aia/issues/$pr/comments?per_page=100") || { echo "#$pr comments unreadable"; exit 1; }
cx=$(jq -rs 'add // [] | [.[]|select(.user.login=="chatgpt-codex-connector[bot]")|.body|select(test("codex-review-state"))][-1] // ""' <<<"$cj" | grep -o '"commit_sha":"[0-9a-f]*","has_any_findings":[a-z]*,"has_unresolved_findings":[a-z]*,"status":"[a-z]*"' | head -1)
case "$cx" in *"\"commit_sha\":\"$sha\""*'"status":"running"'*) grep -qx "$pr" codex-stuck.txt 2>/dev/null || { echo "#$pr Codex still running on head"; exit 1; };; esac
case "$cx" in *"\"commit_sha\":\"$sha\""*'"has_unresolved_findings":false,"status":"completed"'*) ;; *)
  # Codex not clean on the head: the newest stand-in on the head decides, a comment or approval saying
  # "Verdict: clean" (also the way through once Codex's findings are answered and Nigel decided)
  rj=$(gh api --paginate "repos/aianalytics-aia/aia/pulls/$pr/reviews?per_page=100") || { echo "#$pr reviews unreadable"; exit 1; }
  sv=$(jq -rs --arg sha "$sha" 'add // [] | [.[]|select(.commit_id==$sha and (.body|startswith("[Claude review, Codex stand-in]")))] | sort_by(.submitted_at) | last
    | if . == null then "none" elif (.state=="COMMENTED" or .state=="APPROVED") and (.body|test("(?m)^Verdict: clean\\s*$")) then "clean" else "not clean (\(.state))" end' <<<"$rj")
  [ "$sv" = clean ] || { echo "#$pr Codex not clean on head and stand-in review ${sv:-unreadable}: ${cx:-none}"; exit 1; };;
esac
out=$(gh api -X PUT repos/aianalytics-aia/aia/pulls/$pr/merge -f merge_method=merge -f sha=$sha --jq '.sha+" "+(.merged|tostring)') || { echo "#$pr merge failed: $out"; exit 1; }
echo "#$pr MERGED $out"; sed -i "/^$pr:/d" pins.txt; echo "$(date -u +%FT%H:%MZ) #$pr $out" >> merged.log
