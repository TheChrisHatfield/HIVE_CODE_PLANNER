# Microsoft Defender / SmartScreen — portable build

Unsigned PyInstaller apps are often flagged as **PUA** or **Trojan:Win32/Wacatac** until reputation builds. This build is configured to reduce false positives:

- **UPX compression disabled** (packed binaries trigger heuristics)
- **Windows version metadata** embedded in `HivePlanner.exe`
- **SHA256 manifest** (`BUILD-SHA256.txt`) in the distribution folder

## If Defender blocks the app

1. Open **Windows Security → Virus & threat protection → Protection history**
2. Find `HivePlanner.exe` → **Actions → Allow on device** (only if you built or trust the source)
3. Or add an exclusion: **Manage settings → Exclusions → Add folder** → your `HivePlannerPortable` folder

## For IT / enterprise

- Prefer distributing the **onedir folder** (not a single repacked archive from unknown sources)
- Verify hashes against `BUILD-SHA256.txt` from your internal build
- **Code signing** (recommended): build with a trusted Authenticode certificate:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build_portable.ps1 -Sign -CertificatePath "C:\certs\your.pfx" -CertificatePassword (Read-Host -AsSecureString)
```

## Report a false positive to Microsoft

1. [Submit file for analysis](https://www.microsoft.com/en-us/wdsi/filesubmission) — choose *Software developer*
2. Include product name **Hive Planner**, version from `pyproject.toml`, and note *PyInstaller portable build, no UPX*
