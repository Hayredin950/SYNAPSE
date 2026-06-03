import express, { type Express } from "express";
import cors from "cors";
import pinoHttp from "pino-http";
import { createProxyMiddleware } from "http-proxy-middleware";
import router from "./routes";
import { logger } from "./lib/logger";

const app: Express = express();

app.use(
  pinoHttp({
    logger,
    serializers: {
      req(req) {
        return {
          id: req.id,
          method: req.method,
          url: req.url?.split("?")[0],
        };
      },
      res(res) {
        return {
          statusCode: res.statusCode,
        };
      },
    },
  }),
);
app.use(cors());

// Django backend proxy — forwards /api/* to Django at port 8000
// NOTE: Express strips the mount prefix before passing to middleware,
// so we use pathRewrite to restore the full /api/... path that Django expects.
const djangoProxy = createProxyMiddleware({
  target: "http://localhost:8000",
  changeOrigin: true,
  ws: true,
  pathRewrite: (path, _req) => {
    // Express strips "/api" prefix — put it back for Django
    return "/api" + path;
  },
  on: {
    error: (err, req, res) => {
      logger.error({ err }, "Django proxy error");
      if (!res.headersSent) {
        (res as express.Response).status(502).json({
          error: "Backend unavailable",
          detail: "Django backend could not be reached",
        });
      }
    },
  },
});

// Health check handled by the Node router first
app.use("/api/healthz", router);
app.use("/api/health", router);

// Everything else under /api → Django
app.use("/api", djangoProxy);

export default app;
