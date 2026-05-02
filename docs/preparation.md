# Preparation

## 1) Generate hardware profile YAML

Use the helper script and capture output to stdout:

```bash
python3 scripts/print_hardware_profile.py
```

Save it to the default profile file:

```bash
python3 scripts/print_hardware_profile.py > specs/hardware_profiles.yaml
```

Append only one list item to an existing file:

```bash
python3 scripts/print_hardware_profile.py --item-only
```

Useful overrides:

```bash
python3 scripts/print_hardware_profile.py \
  --id benchmark_a100 \
  --label "Benchmark A100 host" \
  --notes "Dedicated benchmark machine"
```

## 2) Attach profile to runs

Pass the profile id in run metadata so aggregate report can map timing rows to hardware:

```bash
python3 -m gripprobe.cli --root . run \
  --shell gptme \
  --model local/qwen2.5:7b \
  --backend ollama \
  --metadata hardware_profile_id=benchmark_a100
```

For suites:

```bash
python3 -m gripprobe.cli --root . run-suite \
  --suite default_cli_matrix \
  --metadata hardware_profile_id=benchmark_a100
```

