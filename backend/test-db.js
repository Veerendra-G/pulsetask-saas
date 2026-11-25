// Standalone Database Connection Tester for Neon PostgreSQL
require('dotenv').config();
const { Pool } = require('pg');

console.log('Testing connection to Neon PostgreSQL...');
console.log('Database URL:', process.env.DATABASE_URL ? process.env.DATABASE_URL.replace(/:[^:@]+@/, ':****@') : 'MISSING!');

if (!process.env.DATABASE_URL || process.env.DATABASE_URL.includes('[YOUR_PASSWORD]')) {
  console.error('\n❌ ERROR: You have not replaced [YOUR_PASSWORD] in your backend/.env file yet!');
  console.log('👉 Please open backend/.env and replace [YOUR_PASSWORD] with your actual Neon password.\n');
  process.exit(1);
}

const pool = new Pool({
  connectionString: process.env.DATABASE_URL,
  ssl: { rejectUnauthorized: false }
});

async function testConnection() {
  try {
    const client = await pool.connect();
    console.log('\n✅ SUCCESS: Connected to Neon PostgreSQL cloud database!');
    
    // Check server time
    const timeRes = await client.query('SELECT NOW() as current_time, version()');
    console.log('📅 Server Time:', timeRes.rows[0].current_time);
    console.log('🐘 PostgreSQL Version:', timeRes.rows[0].version.split(' ')[0], timeRes.rows[0].version.split(' ')[1]);

    // Check tasks table
    const tableRes = await client.query(`
      SELECT table_name 
      FROM information_schema.tables 
      WHERE table_schema = 'public' AND table_name = 'tasks';
    `);

    if (tableRes.rows.length > 0) {
      const countRes = await client.query('SELECT COUNT(*) as total FROM tasks');
      console.log(`📋 Tasks table exists! Current task count: ${countRes.rows[0].total}`);
    } else {
      console.log('ℹ️ Tasks table does not exist yet. It will be auto-created when you run "npm start".');
    }

    client.release();
    pool.end();
    console.log('\n🎉 Everything is working properly! You can now start the backend with "npm start".\n');
  } catch (err) {
    console.error('\n❌ Connection failed:', err.message);
    if (err.message.includes('password authentication failed')) {
      console.log('👉 Tip: Check your password in backend/.env. You can reset it from your Neon console.\n');
    }
    pool.end();
  }
}

testConnection();
