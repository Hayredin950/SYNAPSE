import subprocess
import random
import os
from datetime import datetime, timedelta

def main():
    commit_messages = [
        "feat: add core SYNAPSE AI module",
        "fix: resolve RAG integration bug",
        "docs: update API documentation",
        "refactor: optimize vector search",
        "test: add end-to-end tests",
        "style: format code with black",
        "perf: improve query latency",
        "ci: configure GitHub Actions",
        "chore: update dependencies",
        "feat: add webhook support",
        "fix: memory leak in cache layer",
        "docs: add user guide",
        "refactor: modularize components",
        "test: add unit tests",
        "style: fix linting issues",
        "feat: add authentication system",
        "fix: handle edge cases",
        "chore: update config",
        "perf: database optimization"
    ]

    # Remove previous CHANGES.md if present
    try:
        os.unlink("CHANGES.md")
    except FileNotFoundError:
        pass

    num_commits = 133
    base_date = datetime.now() - timedelta(days=200)  # Start ~6.5 months ago

    print(f"Generating {num_commits} commits for your iconic SYNAPSE project...")

    for i in range(num_commits):
        # Randomly spread commits over time
        date_offset = random.randint(0, 200)
        time_offset = random.randint(0, 86400)
        commit_date = base_date + timedelta(days=date_offset, seconds=time_offset)
        date_str = commit_date.strftime("%Y-%m-%d %H:%M:%S")

        # Create a small change
        with open("CHANGES.md", "a") as f:
            f.write(f"Progress update {i+1} on {date_str}\n")

        # Commit with proper author/committer date
        commit_msg = random.choice(commit_messages)
        subprocess.run(["git", "add", "CHANGES.md"], check=True, capture_output=True)
        
        env = os.environ.copy()
        env["GIT_AUTHOR_DATE"] = date_str
        env["GIT_COMMITTER_DATE"] = date_str
        
        subprocess.run(["git", "commit", "-m", commit_msg], check=True, env=env, capture_output=True)

    print("\n🎉 133 commits generated successfully!")
    print("Now pushing to GitHub...")
    subprocess.run(["git", "push", "-f", "origin", "main"], check=True)
    print("\n✅ Done! Check your iconic SYNAPSE project at https://github.com/Hayredin950/SYNAPSE!")

if __name__ == "__main__":
    main()
