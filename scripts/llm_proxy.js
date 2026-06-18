#!/usr/bin/env node
/**
 * Mini OpenAI-compatible proxy that wraps the z-ai-web-dev-sdk CLI.
 *
 * Listens on http://localhost:8899/v1/chat/completions
 * Accepts the same JSON format as OpenAI API.
 * Forwards to z-ai chat CLI.
 *
 * Usage: node scripts/llm_proxy.js
 */
const http = require('http');
const { execSync } = require('child_process');

const PORT = 8899;

const server = http.createServer((req, res) => {
  if (req.method === 'POST' && req.url === '/v1/chat/completions') {
    let body = '';
    req.on('data', chunk => body += chunk);
    req.on('end', () => {
      try {
        const data = JSON.parse(body);
        const messages = data.messages || [];
        
        // Extract system + user messages
        let systemMsg = 'You are a helpful assistant.';
        let userMsg = '';
        for (const m of messages) {
          if (m.role === 'system') systemMsg = m.content;
          if (m.role === 'user') userMsg = m.content;
        }

        // Build a combined prompt
        const prompt = userMsg;
        
        // Call z-ai CLI with file output (clean JSON, no emoji stdout)
        try {
          const tmpFile = `/tmp/zai_proxy_${Date.now()}.json`;
          execSync(
            `z-ai chat --prompt ${JSON.stringify(prompt)} -o ${tmpFile} 2>/dev/null`,
            { encoding: 'utf-8', timeout: 120000, maxBuffer: 10 * 1024 * 1024 }
          );
          const fs = require('fs');
          const result = fs.readFileSync(tmpFile, 'utf-8');
          fs.unlinkSync(tmpFile);

          // Parse z-ai output (JSON)
          const zaiResult = JSON.parse(result);
          const content = zaiResult.choices?.[0]?.message?.content || '';
          const usage = zaiResult.usage || {};
          
          res.writeHead(200, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({
            id: zaiResult.id || 'chat-proxy-' + Date.now(),
            object: 'chat.completion',
            created: Math.floor(Date.now() / 1000),
            model: data.model || 'glm-4-plus',
            choices: [{
              index: 0,
              message: { role: 'assistant', content },
              finish_reason: 'stop',
            }],
            usage: {
              prompt_tokens: usage.prompt_tokens || 0,
              completion_tokens: usage.completion_tokens || 0,
              total_tokens: usage.total_tokens || 0,
            },
          }));
        } catch (e) {
          res.writeHead(500, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ error: { message: `z-ai error: ${e.message}` } }));
        }
      } catch (e) {
        res.writeHead(400, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ error: { message: `parse error: ${e.message}` } }));
      }
    });
  } else if (req.method === 'GET' && req.url === '/v1/models') {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({
      data: [{ id: 'glm-4-plus', object: 'model' }],
    }));
  } else {
    res.writeHead(404, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ error: { message: 'Not found' } }));
  }
});

server.listen(PORT, '127.0.0.1', () => {
  console.log(`✓ LLM proxy running on http://localhost:${PORT}/v1`);
  console.log(`  OpenAI-compatible endpoint: POST /v1/chat/completions`);
  console.log(`  Backend: z-ai-web-dev-sdk (glm-4-plus)`);
});
