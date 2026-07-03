# Template pictures — teaching the bot to see 👀

The bot recognizes game screens by looking for small "landmark" pictures.
**You make these yourself** — it takes 10 minutes and it's genuinely fun.
(We can't ship them ready-made: they must match YOUR device's exact
screen resolution, or the matching scores drop.)

## The 4 pictures you need

| File name | What to crop | It proves we're on... |
|---|---|---|
| `play_button.png` | the yellow PLAY button | the lobby |
| `in_match.png` | something that ONLY shows during a match — the ammo bar or the super button works well | a match |
| `match_end.png` | the EXIT or CONTINUE button on the defeat/victory screen | the end screen |
| `rewards.png` | the "tap to continue" text on the token/reward screen | the rewards screen |

## How to make one (using the PLAY button as the example)

1. Put the game on the lobby screen.
2. From the project folder, run:
   ```
   python -m yonchbot screenshot
   ```
3. Open the saved picture (it prints the path). In **Preview** on the Mac:
   select a tight rectangle around the PLAY button → Tools → Crop (⌘K).
4. Save it as `play_button.png` **in this folder** (File → Export → PNG).
5. Test it right away:
   ```
   python -m yonchbot find play_button
   ```
   You should see: `🎯 Found it! ... 97% sure.`

## Tips

- Crop **tight** — no background around the button.
- Pick landmarks that never move and never change.
- If `find` says it's not sure enough, try a bigger crop, or lower
  `match_threshold` in `config.yaml` a little (but not too much — the bot
  gets gullible!).
