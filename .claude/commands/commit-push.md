Commit all local changes and push to origin.

## Instructions

1. Run `git status` to see all changes (staged and unstaged)
2. Run `git diff` to review the actual changes
3. Run `git log -3 --oneline` to see recent commit message style
4. Stage all changes with `git add -A`
5. Create a commit with a clear, descriptive message that:
   - Summarizes the nature of the changes (feature, fix, refactor, etc.)
   - Focuses on the "why" rather than the "what"
   - Follows the repository's commit message style
   - Ends with: `Co-Authored-By: Claude <noreply@anthropic.com>`
6. Push to origin with `git push`

## Important

- Do NOT push if there are no changes to commit
- Do NOT include sensitive files (.env, credentials, etc.)
- If push fails due to remote changes, inform the user and ask how to proceed