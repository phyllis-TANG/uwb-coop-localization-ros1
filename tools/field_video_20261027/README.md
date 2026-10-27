# T10 original-video evidence case

Use the specified common baseline `868349b543a03a6a713d1675e1d4ada7d905410c` or this branch's descendant with the same public manifest/geometry/contract. The final submitted sources include each completed stage. Actual execution used the common baseline plus dirty sources; per-stage startup hashes and their limitations are recorded in `source_lineage.json` and `commands.jsonl`.

Dependencies are the unchanged `tools/field_video_20261026/requirements-video.txt`. This tool imports only the pinned prior video primitives and original bag parser. It does not call localization estimators, downloaders, extraction tools or a full-video audit.

The local legacy input root already contains original MOVs, calibration MOVs, T10 bag, PR49 lossless diagnostic frames/PTS and odom exports. Original data are read-only. No media is copied into the new checkout. A different output directory is required for reproduction; every scientific output is created exclusively.

PowerShell example, from this checkout:

```powershell
$env:TEMP = 'I:\UWB\temp'
$env:TMP = 'I:\UWB\temp'
$env:PYTHONIOENCODING = 'utf-8'
$env:PYTHONDONTWRITEBYTECODE = '1'
$pythonPath = 'I:\UWB\project\outputs\video_reference_20261026\venv\Scripts\python.exe'
$legacyPath = 'I:\UWB\project\outputs\video_reference_20261026'
$newOutputPath = 'I:\UWB\project\outputs\video_reference_20261027_reproduction_001'
$newTempPath = 'I:\UWB\temp\video_reference_20261027_reproduction_001'
foreach ($stageName in @('intake','diagnose','geometry','timing','review','metadata','tests')) {
    & $pythonPath tools/field_video_20261027/run_case.py $stageName --legacy $legacyPath --output $newOutputPath --temp $newTempPath
    if ($LASTEXITCODE -ne 0) { throw "Stage failed: $stageName" }
}
```

`intake` verifies only the original assets used by this case, plus T10 bag, and reuses the completed 18-clip QC. `diagnose` reuses matching lossless frames and seeks only selected exact original PTS; it never saves a full video as frames. `geometry` creates conditional diagnostic rows, not accepted references. `timing` reads only original T10 odom/cmd and reuses PTS observations. `review` makes native crop evidence. `metadata` decodes one original first frame from each of T10 and the two checkerboards to verify rotation/timebase. `tests` saves a distinct attempt directory and never deletes failed logs.

`package` is the one-time authoring step used for this delivery. It writes the reference decision, gap table, provenance and independent readback, then seals the new output and copies it into the previously absent `docs/field_tests/20261024_25/video_reference_20261027/`. It refuses an existing delivery. Do not run it in a checkout that already contains the delivered directory; for a new scientific version, choose new versioned output/doc paths in the code/config first. Do not overwrite or delete this result to rerun.

Independent delivered-data readback:

```powershell
& $pythonPath tools/field_video_20261027/verify_case.py --output docs/field_tests/20261024_25/video_reference_20261027
```

The 5 GiB free-space reserve is an execution stop rule, not an estimate for a future large job. I: and process TEMP/TMP must be available as configured. No C: fallback is implemented.

The current explicit operator statement puts Car1's title side forward; decoded installation-image corners 0–1 identify this as canonical +Y. Prior opposite-edge inference stays in provenance and a 180° sensitivity case. Car2 yaw stays unknown and its antenna columns stay empty. Nominal P coordinates, rigid horizontal planes, reported heights and unvalidated intrinsics remain assumptions. Independent Q points are never used to fit or select detectors, orientation, or camera models. Time models remain null and T14/T15 ambiguity families are unchanged.
