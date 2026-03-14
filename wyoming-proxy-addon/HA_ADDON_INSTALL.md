# Installing Wyoming Polyglot Proxy as a Home Assistant Add-on

## Prerequisites

- Home Assistant OS or Supervised installation (add-ons require Supervisor)
- Git repository with the add-on published (GitHub, GitLab, etc.)

## Installation Steps

### Step 1: Verify Repository Structure

Your repository should have this structure:

```
smart-talk/                          # Repository root
├── repository.json                  # Repository metadata
├── wyoming-proxy-addon/            # Add-on directory (must be at root level!)
│   ├── config.yaml                 # ✓ Required
│   ├── Dockerfile                  # ✓ Required
│   ├── README.md                   # ✓ Required
│   ├── CHANGELOG.md                # ✓ Recommended
│   ├── run.sh                      # Entry script
│   ├── requirements.txt            # Python deps
│   └── src/                        # Source code
├── smart-talk-agent/               # Other project files (ignored by HA)
└── smart-talk-integration/         # Other project files (ignored by HA)
```

**Key Points:**
- ✅ Add-on directory (`wyoming-proxy-addon/`) must be at repository ROOT
- ✅ Each add-on directory must contain `config.yaml`, `Dockerfile`, and `README.md`
- ✅ The `slug` in `config.yaml` identifies the add-on

### Step 2: Add Repository to Home Assistant

1. **Navigate to Add-on Store:**
   - Go to **Settings → Add-ons → Add-on Store**
   - Click **⋮** (three dots menu, top-right)
   - Select **Repositories**

2. **Add Repository URL:**
   ```
   https://github.com/giofontana/smart-talk
   ```

   **Important:** Use the repository root URL, NOT the add-on subdirectory!

3. **Click Add** and wait for HA to process the repository

### Step 3: Verify Repository was Added

After adding:
- The page should reload
- You should see "Smart Talk" in your repository list
- Close the repositories dialog

### Step 4: Find and Install Add-on

1. **Refresh Add-on Store:**
   - If not visible, click **⋮ → Reload**
   - Or **⋮ → Check for updates**

2. **Look for the Add-on:**
   - Scroll down past official add-ons
   - Under your repository name ("Smart Talk")
   - Look for "Wyoming Polyglot Proxy"

3. **Install:**
   - Click on "Wyoming Polyglot Proxy"
   - Click **Install**
   - Wait for build to complete (may take 5-10 minutes first time)

## Troubleshooting

### Add-on Doesn't Appear in Store

#### Check 1: Repository URL
✅ Use: `https://github.com/giofontana/smart-talk`
❌ NOT: `https://github.com/giofontana/smart-talk/tree/main/wyoming-proxy-addon`

#### Check 2: config.yaml Syntax
```bash
# Validate YAML syntax
cd /path/to/smart-talk/wyoming-proxy-addon
python3 -c "import yaml; yaml.safe_load(open('config.yaml'))"
```

If this errors, your YAML has syntax issues.

#### Check 3: Branch
HA looks at the **default branch** (usually `main` or `master`). Ensure:
- Your add-on is committed and pushed to the default branch
- Check GitHub: is `wyoming-proxy-addon/` visible on the main page?

#### Check 4: Required Files
Ensure these files exist in `wyoming-proxy-addon/`:
```bash
cd wyoming-proxy-addon
ls -la config.yaml Dockerfile README.md
```

All three must exist.

#### Check 5: config.yaml Must Be Valid

**Common issues:**
- **Quotes:** Don't quote strings unnecessarily
  - ✅ `name: Wyoming Polyglot Proxy`
  - ❌ `name: "Wyoming Polyglot Proxy"`
- **Slug:** Must be lowercase, no spaces
  - ✅ `slug: wyoming-polyglot-proxy`
  - ❌ `slug: "Wyoming Polyglot Proxy"`
- **Version:** Must be quoted
  - ✅ `version: "0.1.0"`
  - ❌ `version: 0.1.0`

#### Check 6: Supervisor Logs

View HA Supervisor logs for errors:

1. **Via UI:**
   - Settings → System → Logs
   - Select "Supervisor" from dropdown
   - Look for repository/add-on loading errors

2. **Via CLI:**
   ```bash
   ha supervisor logs
   ```

### Repository Added But Add-on Not Visible

#### Force Reload
```bash
# SSH into HA or use Terminal add-on
ha addons reload
```

Or via UI:
- Settings → Add-ons → ⋮ → Reload

#### Clear Browser Cache
- Hard refresh: **Ctrl+Shift+R** (Windows/Linux) or **Cmd+Shift+R** (Mac)
- Or open in incognito/private browsing mode

#### Check Repository Configuration

Your `repository.json` should match this format:
```json
{
  "name": "Smart Talk",
  "url": "https://github.com/giofontana/smart-talk",
  "maintainer": "Giovanni Fontana"
}
```

Or convert to `repository.yaml` (modern format):
```yaml
name: Smart Talk
url: https://github.com/giofontana/smart-talk
maintainer: Giovanni Fontana
```

### Build Fails After Installing

#### Check Dockerfile
Ensure Dockerfile builds successfully locally:
```bash
cd wyoming-proxy-addon
podman build -t test-build .
```

#### Check Requirements
All dependencies in `requirements.txt` must be installable:
```bash
pip install -r requirements.txt
```

### Still Not Working?

1. **Remove and Re-add Repository:**
   - Settings → Add-ons → ⋮ → Repositories
   - Remove "Smart Talk" repository
   - Add it again

2. **Check GitHub Repository is Public:**
   - Private repositories won't work unless you've configured SSH keys

3. **Verify Commit:**
   ```bash
   cd /path/to/smart-talk
   git status
   git add wyoming-proxy-addon/
   git commit -m "Add Wyoming Polyglot Proxy add-on"
   git push origin main
   ```

4. **Wait a Few Minutes:**
   - HA caches repository metadata
   - Give it 2-3 minutes after adding repository

## Alternative: Local Add-on (Development)

If GitHub installation isn't working, use local development:

1. **Copy to HA addons directory:**
   ```bash
   scp -r wyoming-proxy-addon/ root@homeassistant.local:/addons/
   ```

2. **In HA UI:**
   - Settings → Add-ons → Add-on Store
   - **Reload** (⋮ menu)
   - Add-on should appear under "Local add-ons"

3. **Install from Local:**
   - Click on the add-on
   - Install

## Verify Installation

After successful install:

1. **Check Add-on Page:**
   - Settings → Add-ons → Wyoming Polyglot Proxy
   - Should show version "0.1.0"
   - Configuration tab should show options

2. **Configure:**
   ```yaml
   whisper_url: tcp://YOUR_WHISPER_IP:10300
   piper_url: tcp://YOUR_PIPER_IP:10200
   voice_mapping:
     en: en_US-lessac-medium
     es: es_ES-mls-medium
     it: it_IT-riccardo-x_low
   log_level: info
   ```

3. **Start:**
   - Click **Start**
   - Check logs for "Wyoming Polyglot Proxy starting"

## Next Steps

Once installed and running:
1. Register Wyoming services (STT/TTS) in HA
2. Create voice assistant using proxy services
3. Test with multiple languages

See [QUICKSTART.md](QUICKSTART.md) for testing and [README.md](README.md) for full documentation.
