# Bug-hunt prediction loop

Print this page in black and white. One shared six-weight vector per repo. No hidden layer.

<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 720 980" font-family="Georgia, Times, serif">
  <rect width="720" height="980" fill="#fff"/>
  <text x="36" y="42" font-size="22" font-family="Arial, Helvetica, sans-serif">Bug-hunt prediction loop</text>
  <text x="36" y="64" font-size="12" fill="#222">Six signals. One linear score. Per repo.</text>

  <rect x="36" y="88" width="648" height="78" fill="none" stroke="#000" stroke-width="1.5"/>
  <text x="52" y="112" font-size="14" font-family="Arial, Helvetica, sans-serif">Seed (bootstrap only)</text>
  <text x="52" y="134" font-size="13">Weights 0.7118, 3.3024, 1.0245, -0.1424, 0, 0. First is log1p of fix commits.</text>
  <text x="52" y="152" font-size="13">Votes halve every 40 voted rows. Not pasted back at full strength.</text>

  <line x1="360" y1="166" x2="360" y2="196" stroke="#000" stroke-width="1.5"/>
  <polygon points="360,196 354,186 366,186" fill="#000"/>

  <rect x="36" y="196" width="648" height="108" fill="none" stroke="#000" stroke-width="2"/>
  <text x="52" y="220" font-size="14" font-family="Arial, Helvetica, sans-serif">System 2 — slow update (stored)</text>
  <text x="52" y="242" font-size="13">Rolling mean of the six weights. One linear layer. No hidden units.</text>
  <text x="52" y="260" font-size="13">Continual backprop = rebuild the mean. Not a second step on the draw.</text>
  <text x="52" y="278" font-size="13">Row decay 0.9 by order. Newest vote = 1. Skipped row = no vote.</text>
  <text x="52" y="296" font-size="13">Commit or review-failed pulls toward the file. Empty pulls away.</text>

  <line x1="360" y1="304" x2="360" y2="334" stroke="#000" stroke-width="1.5"/>
  <polygon points="360,334 354,324 366,324" fill="#000"/>

  <rect x="36" y="334" width="648" height="64" fill="none" stroke="#000" stroke-width="1.5"/>
  <text x="52" y="358" font-size="14" font-family="Arial, Helvetica, sans-serif">Prior</text>
  <text x="52" y="378" font-size="13">The rebuilt mean, plus uncertainty around it. This is what a pass samples.</text>

  <line x1="360" y1="398" x2="360" y2="428" stroke="#000" stroke-width="1.5"/>
  <polygon points="360,428 354,418 366,418" fill="#000"/>

  <rect x="36" y="428" width="648" height="92" fill="none" stroke="#000" stroke-width="1.5" stroke-dasharray="6 4"/>
  <text x="52" y="452" font-size="14" font-family="Arial, Helvetica, sans-serif">System 1 — fast draw (discarded)</text>
  <text x="52" y="474" font-size="13">Thompson sample: one weight per signal, around the mean.</text>
  <text x="52" y="492" font-size="13">Score unopened files. Open the highest. Line churn breaks ties.</text>
  <text x="52" y="510" font-size="13">The draw is not stored and is not an input to the next rebuild.</text>

  <line x1="360" y1="520" x2="360" y2="550" stroke="#000" stroke-width="1.5"/>
  <polygon points="360,550 354,540 366,540" fill="#000"/>

  <rect x="36" y="550" width="310" height="72" fill="none" stroke="#000" stroke-width="1.5"/>
  <text x="52" y="576" font-size="14" font-family="Arial, Helvetica, sans-serif">Bug hunt</text>
  <text x="52" y="598" font-size="13">One file. Fix, skip, empty, or review-failed.</text>

  <line x1="346" y1="586" x2="374" y2="586" stroke="#000" stroke-width="1.5"/>
  <polygon points="374,586 364,580 364,592" fill="#000"/>

  <rect x="374" y="550" width="310" height="72" fill="none" stroke="#000" stroke-width="1.5"/>
  <text x="390" y="576" font-size="14" font-family="Arial, Helvetica, sans-serif">rank-rows.jsonl</text>
  <text x="390" y="598" font-size="13">Append one row after the outcome.</text>

  <path d="M684 586 H700 V240 H690" fill="none" stroke="#000" stroke-width="1.5"/>
  <polygon points="690,240 684,250 696,250" fill="#000"/>
  <text x="612" y="400" font-size="12" transform="rotate(-90 700 400)">next pass rebuilds the mean</text>

  <rect x="36" y="650" width="648" height="132" fill="none" stroke="#000" stroke-width="1"/>
  <text x="52" y="674" font-size="14" font-family="Arial, Helvetica, sans-serif">Decisions kept on the diagram</text>
  <text x="52" y="696" font-size="13">Anchor loosens. Twenty votes block one early bad row. They fade, so later rows can dominate.</text>
  <text x="52" y="716" font-size="13">Decay still remembers about ten real votes. The mean tracks recent outcomes.</text>
  <text x="52" y="736" font-size="13">400 rows is trust that a recovery is stable. It is not a swap and not a stop.</text>
  <text x="52" y="756" font-size="13">System 2 keeps the mean. System 1 throws the draw away.</text>

  <text x="36" y="812" font-size="12">Signals, in order: fix-commit churn, thin or failing test, unwired hop,</text>
  <text x="36" y="828" font-size="12">unread flag, reverted commit, two stores for one fact.</text>
  <text x="36" y="856" font-size="11" fill="#333">Print: black on white. Solid box = stored. Dashed box = used once.</text>
</svg>

## How to read it

Solid boxes are stored. The dashed box is used once and thrown away. The side arrow is the next pass: the new row rebuilds the mean, and the draw does not enter that rebuild.

| Piece | What it is |
| --- | --- |
| Seed | 0.7118, 3.3024, 1.0245, -0.1424, 0, 0. First multiplies log1p of the fix-commit count. 20 imaginary votes at the start |
| Anchor | Those votes halve every 40 voted rows |
| System 2 | Rebuild the mean. Decay 0.9 by row order. This is the continual update |
| Prior | That mean, with uncertainty around it |
| System 1 | One Thompson draw per pass. Rank files. Discard the draw |
| Log | `.hive/bug-hunt/rank-rows.jsonl` after the outcome |
| 400 rows | Trust under one stable process. Not a new fixed vector |
