import { useEffect, useMemo, useState } from 'react';
import type { Asteroid } from '../types/asteroid';
import { computeHohmannTransfer, estimateLaunchWindows } from '../utils/transfer';
import { missionScenario } from '../utils/mining';
import { compositionStory, fmtUsdShort, pickHeadline, sizeComparison } from '../utils/spotlight';

/** When each stage appears, ms after selection. Stage 0 lands during the
 *  camera flight; the rest unfold after arrival (~2.4s). */
const STAGE_DELAYS_MS = [400, 2700, 4500, 6300];

function CountUp({ value, format }: { value: number; format: (n: number) => string }) {
  const [shown, setShown] = useState(0);
  useEffect(() => {
    let raf = 0;
    const start = performance.now();
    const dur = 1400;
    const tick = (now: number) => {
      const t = Math.min((now - start) / dur, 1);
      const p = 1 - Math.pow(1 - t, 3);
      setShown(value * p);
      if (t < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [value]);
  return <span>{format(shown)}</span>;
}

interface Props {
  asteroid: Asteroid;
  dayOffset: number;
}

export function SpotlightStory({ asteroid, dayOffset }: Props) {
  const a = asteroid;
  const [stage, setStage] = useState(-1);

  // The parent remounts this component per asteroid (key={spkid}), so stage
  // starts at -1 naturally and the timers only ever belong to one asteroid.
  useEffect(() => {
    const timers = STAGE_DELAYS_MS.map((ms, i) => setTimeout(() => setStage((s) => Math.max(s, i)), ms));
    return () => timers.forEach(clearTimeout);
  }, [a.spkid]);

  // Freeze the timeline day at selection so "next window" doesn't tick while
  // the panel is unfolding.
  const day0 = useMemo(() => dayOffset, [a.spkid]); // eslint-disable-line react-hooks/exhaustive-deps

  const story = useMemo(() => {
    const comp = compositionStory(a);
    const headline = pickHeadline(a);
    const comparison = sizeComparison(a.diameter_estimated_km);

    let mission = null;
    if (a.a_au && a.inclination_deg != null && a.delta_v_km_s) {
      const tr = computeHohmannTransfer(a.a_au, a.inclination_deg);
      const windows = estimateLaunchWindows(tr.synodic_days, tr.transfer_days, day0);
      const next = windows.find((w) => w.dayOffset >= day0) ?? windows[0];
      const s100 = missionScenario(a, 100_000);
      mission = {
        dv: a.delta_v_km_s,
        travelDays: Math.round(tr.transfer_days),
        nextWindow: next?.date ?? null,
        profit100t: s100.payloadKg > 0 ? s100.profit : null,
        feasible: s100.feasible,
      };
    }
    return { comp, headline, comparison, mission };
  }, [a, day0]);

  const stageCls = (i: number) => `spotlight-stage${stage >= i ? ' visible' : ''}`;

  return (
    <div className="spotlight-story" onClick={() => setStage(3)}>
      <div className={stageCls(0)}>
        <div className="spotlight-eyebrow">Now approaching</div>
        <div className="spotlight-name">{a.name}</div>
        <div className="spotlight-chips">
          {a.orbit_class && <span className="spotlight-chip">{a.orbit_class}</span>}
          {a.neo === 'Y' && <span className="spotlight-chip">NEO</span>}
          {a.pha === 'Y' && <span className="spotlight-chip spotlight-chip--warn">PHA</span>}
          {a.economic_priority_rank != null && (
            <span className="spotlight-chip">Rank #{a.economic_priority_rank.toLocaleString()}</span>
          )}
        </div>
      </div>

      <div className={stageCls(1)}>
        <div className="spotlight-comp-title">{story.comp.title}</div>
        <div className="spotlight-comp-blurb">
          {story.comp.blurb}
          {a.composition_confidence != null && (
            <span className="spotlight-confidence"> ({Math.round(a.composition_confidence * 100)}% confidence)</span>
          )}
        </div>
        {a.diameter_estimated_km != null && (
          <div className="spotlight-scale">
            {a.diameter_estimated_km < 1
              ? a.diameter_estimated_km.toFixed(2)
              : a.diameter_estimated_km.toFixed(1)} km across{story.comparison ? ` — ${story.comparison}` : ''}
          </div>
        )}
      </div>

      {story.headline && (
        <div className={stageCls(2)}>
          <div className="spotlight-number">
            {stage >= 2 && <CountUp value={story.headline.value} format={story.headline.format} />}
          </div>
          <div className="spotlight-caption">{story.headline.caption}</div>
          {story.headline.footnote && (
            <div className="spotlight-footnote">{story.headline.footnote}</div>
          )}
        </div>
      )}

      {story.mission && (
        <div className={stageCls(3)}>
          <div className="spotlight-mission-title">The mission</div>
          <div className="spotlight-mission-row">
            <span>Δv from Earth</span><b>{story.mission.dv.toFixed(2)} km/s</b>
          </div>
          <div className="spotlight-mission-row">
            <span>Travel time</span><b>~{story.mission.travelDays} days</b>
          </div>
          {story.mission.nextWindow && (
            <div className="spotlight-mission-row">
              <span>Next launch window</span><b>{story.mission.nextWindow}</b>
            </div>
          )}
          {story.mission.profit100t != null && (
            <div className="spotlight-mission-row">
              <span>100 t mission profit</span>
              <b className={story.mission.feasible ? 'profit-positive' : 'profit-negative'}>
                {fmtUsdShort(story.mission.profit100t)}
              </b>
            </div>
          )}
          <div className="spotlight-footnote">Model estimates, upper bounds — see Methodology.</div>
        </div>
      )}
    </div>
  );
}
