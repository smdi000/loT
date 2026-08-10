/** @typedef {import("@tuya-sat/micro-script").DebuggerConfig} DebuggerConfig */
/** @typedef {import("@tuya-sat/micro-script").WebpackCombineFunction} WebpackCombineFunction */
/** @typedef {import("@tuya-sat/micro-script").CustomDevServer} CustomDevServer */

module.exports = {
  /** @type {DebuggerConfig} */
  debuggerConfig: {
    // The dev proxy routes browser /custom-api requests to the accepted ECS API.
    // React business code contains only the relative path, never this host.
    customApiUrl: 'http://47.250.160.90',
    logSign: false,
    mockPermissions: [],
    additionHeaders: {},
  },
  /** @type {WebpackCombineFunction} */
  webpack(config, { isDev }) {
    config.output.publicPath = isDev ? '/' : './';
    return config;
  },
  // micro-script 3.2 mounts its standalone SPA fallback before the built-in
  // custom-api proxy in --main mode. Mount the same proxy early so local
  // Hybrid Runtime debugging preserves the official /custom-api contract.
  mainServer: {
    before(app) {
      const { createProxyMiddleware } = require('http-proxy-middleware');
      const target = module.exports.debuggerConfig.customApiUrl;
      app.use('/custom-api', createProxyMiddleware({
        target,
        secure: false,
        changeOrigin: true,
        pathRewrite: { '^/custom-api': '' },
      }));
    },
  },
  /** @type {CustomDevServer} */
  devServer(config) {
    const { createProxyMiddleware } = require('http-proxy-middleware');
    const originalSetup = config.setupMiddlewares;
    config.setupMiddlewares = (middlewares, server) => {
      // The standalone bundle server does not pass through mainServer.before.
      // Register the same local-only custom API proxy before the SPA fallback.
      server.app.use('/custom-api', createProxyMiddleware({
        target: module.exports.debuggerConfig.customApiUrl,
        secure: false,
        changeOrigin: true,
        pathRewrite: { '^/custom-api': '' },
      }));
      return originalSetup ? originalSetup(middlewares, server) : middlewares;
    };
    return config;
  },
};
