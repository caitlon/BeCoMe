import { defineRailway, github, project, service } from "railway/iac";

// Owns the backend and frontend services only. Databases, Redis, volumes and
// buckets are not declared here, and a named partial never deletes what it
// does not own. Variables stay unmanaged: they live in Railway, not in git.
export const partial = "app";

// Each environment has its own services, named after it, and deploys from the
// branch of the same name.
const ENVIRONMENTS = ["dev", "test", "prod"] as const;
type Environment = (typeof ENVIRONMENTS)[number];

function environmentOf(name: string | undefined): Environment {
  const env = ENVIRONMENTS.find((candidate) => candidate === name);
  if (env === undefined) {
    throw new Error(`Unknown Railway environment: ${name}`);
  }
  return env;
}

export default defineRailway((ctx) => {
  const env = environmentOf(ctx.environment);
  // dev and test sleep when idle to save cost; prod never sleeps.
  const deploy = {
    // Restart on failure: Railway's default policy, which it stores as null,
    // so only the retry cap is set here.
    restartPolicyMaxRetries: 3,
    sleepApplication: env === "prod" ? null : true,
  } as const;

  const backend = service(`${env}-backend`, {
    source: github("caitlon/BeCoMe", { branch: env, checkSuites: true }),
    build: { builder: "DOCKERFILE", dockerfilePath: "docker/Dockerfile" },
    // Apply database migrations once per deploy, before the new version goes
    // live. Runs as a single one-off (no per-worker race); a failure blocks the
    // deploy.
    preDeploy: "alembic upgrade head",
    healthcheck: "/api/v1/health",
    healthcheckTimeout: 30,
    // Pin to a single replica: scale intentionally, never accidentally. One
    // uvicorn worker per replica (see UVICORN_WORKERS in docker/Dockerfile)
    // keeps the memory footprint predictable and bounded on Railway.
    replicas: { "europe-west4-drams3a": 1 },
    deploy,
  });

  // The frontend builds from its own directory; dockerfilePath resolves
  // against the root directory, so this is frontend/Dockerfile.
  const frontend = service(`${env}-frontend`, {
    source: github("caitlon/BeCoMe", {
      branch: env,
      checkSuites: true,
      rootDirectory: "/frontend",
    }),
    build: { builder: "DOCKERFILE", dockerfilePath: "Dockerfile" },
    healthcheck: "/",
    healthcheckTimeout: 30,
    replicas: { "europe-west4-drams3a": 1 },
    deploy,
  });

  return project("become-api", {
    // Read by the Railway CLI; not in the SDK's ProjectDefinition type.
    // @ts-expect-error -- see above
    variables: { managed: false },
    resources: [backend, frontend],
  });
});
