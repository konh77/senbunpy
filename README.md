# 千分の一の国 — senbunpy

A simulation of Japan at one-thousandth scale: about 124,000 simulated people,
built from real age-structure data, who earn, spend, pay tax and age month by
month — and a small language for writing the laws that govern them.

You write a law in the *官報* (gazette) panel, run the clock forward, and watch
seven national indicators react.

## What is in here

| Path | What it does |
| --- | --- |
| `engine/` | The simulation: population, income, consumption, tax, government, ledger, metrics |
| `dsl/` | A small language for laws — lexer, parser, validator, compiler |
| `laws/` | Laws written in that language |
| `web/` | The browser interface, including the 3D city view |
| `server/` | The HTTP server that runs a simulation and serves the interface |
| `tools/` | Fetches real population data from Japan's e-Stat API |
| `data/` | Cached statistics so the simulation runs without network access |

`千分の一の国ー操作方法.md` is the user guide, in Japanese.

## Running it

```bash
pip install -r requirements.txt -r requirements-server.txt
python build_init.py        # build the initial population from the cached data
python -m server            # then open the address it prints
```

Refreshing the statistics yourself needs a free
[e-Stat](https://www.e-stat.go.jp/) API key:

```bash
mkdir -p ~/.config/senbunpy
echo 'ESTAT_APP_ID=your_key_here' > ~/.config/senbunpy/estat.env
chmod 600 ~/.config/senbunpy/estat.env
python tools/estat_fetch.py
```

The key is read from that file and never stored in the repository.

## Design notes

**Money is conserved.** Every yen that leaves one account arrives in another,
and the ledger asserts it. A simulation that quietly creates money tells you
comforting lies.

**Runs are deterministic.** The same seed and the same laws give the same
history, which is what makes comparing two policies meaningful rather than
anecdotal. There is a test for it.

**The population is real.** Age structure comes from e-Stat rather than a
convenient curve, because the shape of Japan's population *is* the interesting
part.

## Status

An archived experiment, published as-is. It runs, the tests pass, and it is not
maintained.

## Licence

MIT — see [LICENSE](./LICENSE).
