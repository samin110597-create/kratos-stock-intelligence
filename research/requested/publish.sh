set -eu
# Stage only this worker's output, never shared research indexes.
git config user.name 'github-actions[bot]'
git config user.email '41898282+github-actions[bot]@users.noreply.github.com'
if [ -d site/data/requested ]; then git add -f site/data/requested; fi
if git diff --cached --quiet; then exit 0; fi
git commit -m "Record requested ticker research"
# Discard only transient index rewrites in the disposable workflow checkout.
git restore --worktree .
for i in 1 2 3 4 5; do
  git pull --rebase origin main
  if git push origin HEAD:main; then exit 0; fi
  sleep "$((2*i))"
done
exit 1
