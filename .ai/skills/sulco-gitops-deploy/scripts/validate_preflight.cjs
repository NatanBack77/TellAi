#!/usr/bin/env node
/**
 * validate_preflight.cjs - Pre-flight GitOps release and secrets hygiene validator
 * Usage: node validate_preflight.cjs [--repo-dir ./sulco-nasa]
 */

const { execSync } = require('child_process');
const fs = require('fs');
const path = require('path');

function parseArgs() {
  const args = process.argv.slice(2);
  let repoDir = './sulco-nasa';
  for (let i = 0; i < args.length; i++) {
    if (args[i] === '--repo-dir' && args[i + 1]) repoDir = args[++i];
  }
  return path.resolve(repoDir);
}

function runGit(cmd, cwd) {
  try {
    return execSync(`git ${cmd}`, { cwd, encoding: 'utf-8', stdio: ['pipe', 'pipe', 'pipe'] }).trim();
  } catch (err) {
    return null;
  }
}

function auditRepository(repoPath) {
  const checks = [];
  let allPass = true;

  // 1. Check Git Status
  const status = runGit('status --porcelain', repoPath);
  const isClean = status === '';
  checks.push({
    name: 'Git Working Tree Cleanliness',
    passed: isClean,
    details: isClean ? 'Clean working tree' : 'Uncommitted or unstaged changes detected'
  });
  if (!isClean) allPass = false;

  // 2. Check Git Author & Email
  const authorName = runGit('config user.name', repoPath);
  const authorEmail = runGit('config user.email', repoPath);
  const emailValid = authorEmail === 'contato@antenorpires.eng.br';
  checks.push({
    name: 'Author Identity Alignment',
    passed: emailValid,
    details: `Author: ${authorName} <${authorEmail}> (Expected: Antenor Pires <contato@antenorpires.eng.br>)`
  });
  if (!emailValid) allPass = false;

  // 3. Scan for Secret Leaks in Tracked Files
  const trackedFiles = runGit('ls-files', repoPath) || '';
  const leakPatterns = [
    /\.env$/i,
    /\.pat$/i,
    /id_rsa/i,
    /\.pem$/i
  ];

  const suspiciousFiles = trackedFiles.split('\n').filter(f => leakPatterns.some(p => p.test(f)));
  const noSecretFiles = suspiciousFiles.length === 0;
  checks.push({
    name: 'Secret & Credential Files Protection',
    passed: noSecretFiles,
    details: noSecretFiles ? 'No credential files (.env, .pat, .pem) tracked' : `LEAK DETECTED: ${suspiciousFiles.join(', ')}`
  });
  if (!noSecretFiles) allPass = false;

  // 4. Check Current Branch
  const branch = runGit('rev-parse --abbrev-ref HEAD', repoPath);
  const branchSafe = branch && branch !== 'main';
  checks.push({
    name: 'Feature Branch Isolation',
    passed: branchSafe,
    details: `Active Branch: '${branch}' (Direct commits to 'main' discouraged)`
  });

  return {
    timestamp: new Date().toISOString(),
    repository: repoPath,
    verdict: allPass ? 'READY_FOR_DEPLOY' : 'ACTION_REQUIRED',
    checks
  };
}

const targetDir = parseArgs();
const report = auditRepository(targetDir);
console.log(JSON.stringify(report, null, 2));
process.exit(report.verdict === 'READY_FOR_DEPLOY' ? 0 : 1);
