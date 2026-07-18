#!/usr/bin/env node

import { createRequire } from 'node:module';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { pathToFileURL } from 'node:url';

function parseArgs(argv) {
  const args = {};
  for (let index = 0; index < argv.length; index += 1) {
    const key = argv[index];
    if (!key.startsWith('--')) continue;
    args[key.slice(2)] = argv[index + 1];
    index += 1;
  }
  return args;
}

function normalizeSourceUrl(url, baseUrl, uiRoot) {
  const base = `${baseUrl.replace(/\/$/, '')}/`;
  let value = url.startsWith(base) ? url.slice(base.length) : url;
  const filePrefix = `@fs${uiRoot}`.replaceAll('\\', '/').replace(/\/$/, '') + '/';
  if (value.startsWith('src/')) return `apps/web-antd/${value}`;
  if (value.startsWith(filePrefix)) return value.slice(filePrefix.length);
  return value;
}

function normalizeApiPath(url) {
  const parsed = new URL(url);
  const marker = '/admin-api';
  const index = parsed.pathname.indexOf(marker);
  if (index < 0) return null;
  return parsed.pathname.slice(index + marker.length) || '/';
}

function joinRoutePath(parent, child) {
  if (!child) return parent || '/';
  if (child.startsWith('/')) return child;
  if (!parent || parent === '/') return `/${child}`;
  return `${parent.replace(/\/$/, '')}/${child}`;
}

function flattenMenuRoutes(nodes, parent = '') {
  const rows = [];
  for (const node of nodes ?? []) {
    const fullPath = joinRoutePath(parent, node.path ?? '');
    const hasVisibleComponentChild = (node.children ?? []).some(
      (child) => child.component && child.visible !== false,
    );
    if (node.component && !hasVisibleComponentChild) {
      rows.push({
        id: `live.${String(node.component).replaceAll('/', '.').replace(/\.vue$/, '')}`,
        goal: node.name ?? node.component,
        path: fullPath,
        component: node.component,
        visible: node.visible !== false,
        source: 'live-menu',
      });
    }
    rows.push(...flattenMenuRoutes(node.children, fullPath));
  }
  return rows;
}

async function discoverRoutes({ baseUrl, tenantId, username, password, policy }) {
  if (!policy?.enabled) return [];
  const headers = { 'content-type': 'application/json', 'tenant-id': String(tenantId) };
  const loginResponse = await fetch(`${baseUrl}/admin-api/system/auth/login`, {
    method: 'POST',
    headers,
    body: JSON.stringify({ username, password }),
  });
  const loginPayload = await loginResponse.json();
  const accessToken = loginPayload?.data?.accessToken;
  if (!accessToken) throw new Error(`live route discovery login failed: ${loginPayload?.msg ?? loginResponse.status}`);
  const permissionResponse = await fetch(`${baseUrl}/admin-api/system/auth/get-permission-info`, {
    headers: { ...headers, authorization: `Bearer ${accessToken}` },
  });
  const permissionPayload = await permissionResponse.json();
  if (permissionPayload?.code !== 0) {
    throw new Error(`live route discovery failed: ${permissionPayload?.msg ?? permissionResponse.status}`);
  }
  const domains = new Set(policy.domains ?? []);
  return flattenMenuRoutes(permissionPayload.data?.menus)
    .filter((route) => !policy.visible_only || route.visible)
    .filter((route) => domains.has(String(route.component).split('/', 1)[0]))
    .slice(0, policy.maximum ?? 100);
}

function collectCoverage(entries, baseUrl, uiRoot) {
  const files = [];
  for (const entry of entries) {
    if (!entry.url || !entry.url.startsWith(baseUrl)) continue;
    const file = normalizeSourceUrl(entry.url, baseUrl, uiRoot);
    if (!file.startsWith('apps/web-antd/src/') && !file.startsWith('packages/') && !file.startsWith('internal/')) {
      continue;
    }
    const functions = [];
    for (const item of entry.functions ?? []) {
      const rootRange = item.ranges?.[0];
      if (!rootRange) continue;
      functions.push({
        id: `${rootRange.startOffset}:${rootRange.endOffset}:${item.functionName || '<anonymous>'}`,
        name: item.functionName || '<anonymous>',
        start: rootRange.startOffset,
        end: rootRange.endOffset,
        executed: rootRange.count > 0,
      });
    }
    files.push({ file: file.split('?', 1)[0], functions });
  }
  return files;
}

function mergeCoverage(routeRows) {
  const merged = new Map();
  for (const route of routeRows) {
    for (const fileRow of route.coverage) {
      if (!merged.has(fileRow.file)) merged.set(fileRow.file, new Map());
      const functions = merged.get(fileRow.file);
      for (const item of fileRow.functions) {
        const previous = functions.get(item.id);
        functions.set(item.id, { ...item, executed: item.executed || previous?.executed || false });
      }
    }
  }
  const files = [...merged.entries()].map(([file, functions]) => {
    const values = [...functions.values()];
    const executedFunctions = values.filter((item) => item.executed).length;
    return {
      file,
      functions: values.length,
      executed_functions: executedFunctions,
      uncovered_functions: values.length - executedFunctions,
      function_coverage_pct: values.length ? Number(((executedFunctions * 100) / values.length).toFixed(2)) : 0,
    };
  });
  const total = files.reduce((sum, row) => sum + row.functions, 0);
  const executed = files.reduce((sum, row) => sum + row.executed_functions, 0);
  const appFiles = files.filter((row) => row.file.startsWith('apps/web-antd/src/'));
  const appTotal = appFiles.reduce((sum, row) => sum + row.functions, 0);
  const appExecuted = appFiles.reduce((sum, row) => sum + row.executed_functions, 0);
  return {
    files,
    summary: {
      loaded_source_files: files.length,
      transformed_functions: total,
      executed_transformed_functions: executed,
      uncovered_transformed_functions: total - executed,
      transformed_function_coverage_pct: total ? Number(((executed * 100) / total).toFixed(2)) : 0,
      loaded_app_source_files: appFiles.length,
      app_transformed_functions: appTotal,
      app_executed_transformed_functions: appExecuted,
      app_transformed_function_coverage_pct: appTotal
        ? Number(((appExecuted * 100) / appTotal).toFixed(2))
        : 0,
    },
  };
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const uiRoot = path.resolve(args['ui-root'] ?? '');
  const baseUrl = (args['base-url'] ?? 'http://127.0.0.1:5666').replace(/\/$/, '');
  const scenarioPath = path.resolve(args.scenario ?? '');
  const outputPath = path.resolve(args.output ?? 'runtime.json');
  const username = process.env.CLOUDMOLD_QA_USERNAME;
  const password = process.env.CLOUDMOLD_QA_PASSWORD;
  if (!uiRoot || !scenarioPath || !username || !password) {
    throw new Error('ui-root, scenario, CLOUDMOLD_QA_USERNAME and CLOUDMOLD_QA_PASSWORD are required');
  }

  const scenario = JSON.parse(await readFile(scenarioPath, 'utf8'));
  const requireFromUi = createRequire(pathToFileURL(path.join(uiRoot, 'package.json')));
  const { chromium } = requireFromUi('playwright');
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext();
  const page = await context.newPage();

  try {
    await page.goto(`${baseUrl}/auth/login`, { waitUntil: 'domcontentloaded' });
    await page.getByPlaceholder('请输入用户名').fill(username);
    await page.getByPlaceholder('请输入密码').fill(password);
    await page.getByRole('button', { name: 'login', exact: true }).click();
    await page.waitForURL((url) => !url.pathname.includes('/auth/login'), { timeout: 30_000 });

    const discoveredRoutes = await discoverRoutes({
      baseUrl,
      tenantId: args['tenant-id'] ?? 1,
      username,
      password,
      policy: scenario.discover_live_routes,
    });
    const routeMap = new Map();
    for (const route of discoveredRoutes) routeMap.set(route.path, route);
    for (const route of scenario.critical_routes) {
      routeMap.set(route.path, {
        ...(routeMap.get(route.path) ?? {}),
        ...route,
        source: routeMap.has(route.path) ? 'live-menu+critical' : 'critical',
      });
    }
    const routesToVisit = [...routeMap.values()];

    const routeRows = [];
    for (const route of routesToVisit) {
      const routeCalls = [];
      const failures = [];
      const assetFailures = [];
      const pageErrors = [];
      const consoleErrors = [];
      const responseListener = (response) => {
        const apiPath = normalizeApiPath(response.url());
        if (!apiPath) return;
        const row = {
          method: response.request().method(),
          path: apiPath,
          status: response.status(),
        };
        routeCalls.push(row);
        if (response.status() >= 400) {
          if (row.method === 'GET' && row.path.startsWith('/infra/file/')) assetFailures.push(row);
          else failures.push(row);
        }
      };
      page.on('response', responseListener);
      const pageErrorListener = (error) => pageErrors.push(String(error?.message ?? error));
      const consoleListener = (message) => {
        if (message.type() === 'error') consoleErrors.push(message.text());
      };
      page.on('pageerror', pageErrorListener);
      page.on('console', consoleListener);

      const cdp = await context.newCDPSession(page);
      await cdp.send('Profiler.enable');
      await cdp.send('Profiler.startPreciseCoverage', {
        callCount: true,
        detailed: true,
        allowTriggeredUpdates: false,
      });
      await page.goto(`${baseUrl}${route.path}`, { waitUntil: 'domcontentloaded' });
      await page
        .waitForFunction(
          () => !document.body.textContent?.includes('加载菜单中...'),
          undefined,
          { timeout: scenario.route_ready_timeout_ms ?? 15_000 },
        )
        .catch(() => {});
      await page.waitForLoadState('networkidle', { timeout: 10_000 }).catch(() => {});
      await page.waitForTimeout(scenario.route_wait_ms ?? 1200);
      const rawCoverage = await cdp.send('Profiler.takePreciseCoverage');
      await cdp.send('Profiler.stopPreciseCoverage');
      await cdp.send('Profiler.disable');
      await cdp.detach();
      page.off('response', responseListener);
      page.off('pageerror', pageErrorListener);
      page.off('console', consoleListener);

      const state = await page.evaluate(() => ({
        actual_path: window.location.pathname,
        title: document.title,
        tables: document.querySelectorAll('table').length,
        forms: document.querySelectorAll('form').length,
        error_boundary: document.body.textContent?.includes('内部服务器错误，请稍后再试。') ?? false,
        menu_loading: document.body.textContent?.includes('加载菜单中...') ?? false,
      }));
      const uniqueCalls = [...new Map(routeCalls.map((item) => [`${item.method} ${item.path}`, item])).values()];
      const routePathMatches = state.actual_path.replace(/\/$/, '') === route.path.replace(/\/$/, '');
      const emptyRoute =
        state.title === '芋道管理系统' && state.tables === 0 && state.forms === 0;
      routeRows.push({
        id: route.id,
        goal: route.goal,
        path: route.path,
        component: route.component ?? null,
        route_source: route.source,
        ...state,
        route_path_matches: routePathMatches,
        empty_route: emptyRoute,
        passed:
          routePathMatches &&
          !emptyRoute &&
          !state.error_boundary &&
          !state.menu_loading &&
          pageErrors.length === 0 &&
          failures.length === 0,
        api_calls: uniqueCalls,
        failed_api_calls: failures,
        asset_failures: assetFailures,
        page_errors: [...new Set(pageErrors)],
        console_errors: [...new Set(consoleErrors)],
        coverage: collectCoverage(rawCoverage.result ?? [], baseUrl, uiRoot),
      });
    }

    const merged = mergeCoverage(routeRows);
    const report = {
      schema_version: 'cloudmold.ui-runtime-coverage/v1',
      scenario_id: scenario.scenario_id,
      base_url: baseUrl,
      tenant_id: args['tenant-id'] ?? null,
      read_only: true,
      summary: {
        routes: routeRows.length,
        discovered_live_routes: discoveredRoutes.length,
        critical_routes: scenario.critical_routes.length,
        passed_routes: routeRows.filter((row) => row.passed).length,
        failed_routes: routeRows.filter((row) => !row.passed).length,
        warning_routes: routeRows.filter((row) => row.asset_failures.length > 0).length,
        missing_assets: routeRows.reduce((sum, row) => sum + row.asset_failures.length, 0),
        unique_api_calls: new Set(routeRows.flatMap((row) => row.api_calls.map((item) => `${item.method} ${item.path}`))).size,
        ...merged.summary,
        caveat: 'Chromium transformed-function smoke coverage; not source-line coverage',
      },
      routes: routeRows.map(({ coverage, ...row }) => row),
      files: merged.files.sort((left, right) => left.function_coverage_pct - right.function_coverage_pct),
    };
    await mkdir(path.dirname(outputPath), { recursive: true });
    await writeFile(outputPath, `${JSON.stringify(report, null, 2)}\n`, 'utf8');
    process.stdout.write(`${JSON.stringify(report.summary)}\n`);
    if (report.summary.failed_routes > 0) process.exitCode = 1;
  } finally {
    await browser.close();
  }
}

await main();
