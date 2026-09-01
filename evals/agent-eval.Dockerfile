# Reproducible container for running LIVE fastskill skill evals against a real agent.
#
#   docker build -f evals/agent-eval.Dockerfile -t fastskill-evals .
#   docker run --rm -e OPENAI_API_KEY=$OPENAI_API_KEY     fastskill-evals codex
#   docker run --rm -e ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY fastskill-evals claude
#
# Agent keys the CLI knows: aikit, claude, codex, cursor, gemini, pi. This image installs only
# codex and claude; extend the `npm install -g` line below before passing another key.
FROM node:20-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates git \
    && rm -rf /var/lib/apt/lists/*

# FastSkill CLI (installs to /usr/local/bin)
RUN curl -fsSL https://raw.githubusercontent.com/gofastskill/fastskill/main/scripts/install.sh | bash \
    && fastskill --version

# Agent CLIs (codex needs OPENAI_API_KEY, claude needs ANTHROPIC_API_KEY at runtime)
RUN npm install -g @openai/codex @anthropic-ai/claude-code

WORKDIR /skill
COPY . /skill

# Arg 1 = agent key (default codex). Runs the full suite and writes artifacts to /skill/eval-runs.
ENTRYPOINT ["bash", "-lc", "cd fastskill && fastskill eval run --agent \"${1:-codex}\" --output-dir ../eval-runs", "--"]
