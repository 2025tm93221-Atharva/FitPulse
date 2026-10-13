# Jenkins CI

The root `Jenkinsfile` provides an additional build and quality gate alongside
GitHub Actions. It runs against the GitHub revision that triggered the build,
performs a clean checkout, validates both applications, checks database
migrations, and builds both Docker images locally. It does not push images or
use staging/production credentials.

## Jenkins agent prerequisites

Create an agent with the Jenkins label `fitpulse-ci` and install:

- Git
- Docker CLI and a Docker daemon the agent is permitted to use

Install Node.js 22 and npm on the agent and make both executables available on
the agent's `PATH`. The frontend stage checks that both commands exist and
that the Node.js major version is 22 before running `npm ci`.

The Jenkins controller needs Pipeline and GitHub Branch Source support. Keep
builds on an isolated CI agent, not the controller. The agent needs enough disk
space for dependency installs and Docker image layers.

## Create the GitHub job

1. Install the **Pipeline: Multibranch** and **GitHub Branch Source** plugins.
2. Create **New Item → Multibranch Pipeline** in Jenkins.
3. Under **Branch Sources**, add the GitHub repository
   `2025tm93221-Atharva/FitPulse`. Add a Jenkins GitHub App or least-privilege
   GitHub credential if the repository is private.
4. Configure branch discovery and pull-request discovery for the repository.
   The Jenkinsfile is at the repository root; leave the Script Path as
   `Jenkinsfile`.
5. Ensure Jenkins can be reached by GitHub over HTTPS and configure the
   GitHub Branch Source webhook integration (or configure the repository's
   webhook to point to the Jenkins GitHub webhook endpoint). Subscribe to
   push and pull-request events, then run **Scan Multibranch Pipeline Now**
   once to discover branches and open pull requests.
6. Confirm the job uses an agent with the `fitpulse-ci` label.

For a private repository, configure checkout credentials in Jenkins' branch
source settings. Do not put access tokens, deployment secrets, or production
environment files in the repository or Jenkinsfile. This pipeline does not
need application runtime secrets.

## Pull request isolation

Pull requests can change the Jenkinsfile and Docker build instructions. Do not
run untrusted fork pull requests on an agent that has production access or
unrestricted access to a shared Docker daemon. Use disposable isolated agents
for those builds, or configure pull-request discovery to build only trusted
contributors' pull requests.

## Pipeline stages

- **Clean checkout** removes the previous workspace before checking out the
  exact revision supplied by the multibranch job.
- **Frontend quality gate** runs `npm ci`, ESLint, Vitest, and the Vite
  production build.
- **Backend quality gate** runs in a disposable Python 3.14 Docker container,
  installs dependencies from `backEnd/requirements.txt` and Ruff, checks
  Python syntax, runs pytest, and applies/checks migrations against a fresh
  SQLite database. Python does not need to be installed on the Jenkins agent.
- **Docker image builds** builds the backend and frontend images without
  publishing them. The tag includes the Jenkins build identity so parallel
  branches do not reuse the same image tag.

Any failed command fails the build and prevents later stages from running.
