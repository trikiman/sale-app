/**
 * VkusVill Scraper with VLESS Proxy
 */
const puppeteer = require('puppeteer-extra');
const StealthPlugin = require('puppeteer-extra-plugin-stealth');
const fs = require('fs');
const { execSync, spawn } = require('child_process');

puppeteer.use(StealthPlugin());

const COOKIES_FILE = 'cookies.json';
const PROXY = 'socks5://127.0.0.1:1080';

async function startXray() {
    console.log('Starting Xray proxy...');

    // Download xray if not exists
    if (!fs.existsSync('./xray')) {
        console.log('Downloading Xray...');
        try {
            // Use curl instead of wget
            execSync('curl -L -o xray.zip https://github.com/XTLS/Xray-core/releases/download/v1.8.4/Xray-linux-64.zip');
            execSync('unzip -o xray.zip xray');
            execSync('chmod +x xray');
            execSync('rm xray.zip');
        } catch (e) {
            console.log('Error downloading Xray:', e.message);
            return false;
        }
    }

    // Start xray in background
    const xray = spawn('./xray', ['run', '-c', 'xray_config.json'], {
        detached: true,
        stdio: 'ignore'
    });
    xray.unref();

    // Wait for proxy to start
    await new Promise(r => setTimeout(r, 3000));
    console.log('Xray proxy started on port 1080');
    return true;
}

async function scrape() {
    console.log('========================================');
    console.log('VkusVill Scraper (with VLESS Proxy)');
    console.log('========================================');

    if (!fs.existsSync(COOKIES_FILE)) {
        console.log('ERROR: Upload cookies.json first!');
        return;
    }

    const cookies = JSON.parse(fs.readFileSync(COOKIES_FILE, 'utf8'));
    console.log(`Loaded ${cookies.length} cookies`);

    // Start proxy
    const proxyStarted = await startXray();
    if (!proxyStarted) {
        console.log('Failed to start proxy');
        return;
    }

    try {
        console.log('Starting browser with proxy...');

        const browser = await puppeteer.launch({
            headless: 'new',
            args: [
                '--no-sandbox',
                '--disable-setuid-sandbox',
                `--proxy-server=${PROXY}`,
                '--lang=ru-RU'
            ]
        });

        const page = await browser.newPage();
        await page.setViewport({ width: 1920, height: 1080 });

        console.log('Setting cookies...');
        await page.setCookie(...cookies);

        console.log('Opening VkusVill cart...');
        await page.goto('https://vkusvill.ru/cart/', {
            waitUntil: 'networkidle2',
            timeout: 60000
        });

        await new Promise(r => setTimeout(r, 5000));

        const title = await page.title();
        console.log(`Page title: ${title}`);

        if (title.includes('403') || title.includes('Forbidden')) {
            console.log('BLOCKED!');
        } else {
            console.log('SUCCESS!');
            const content = await page.content();
            if (content.includes('Зелёные ценники')) {
                console.log('Green prices found!');
            }
        }

        await browser.close();

    } catch (error) {
        console.log('Error:', error.message);
    }
}

scrape();
