// Vercel Serverless Function entry point for PulseTask
// Automatically wraps the Express app as a serverless microservice
const app = require('../backend/server.js');

module.exports = app;
