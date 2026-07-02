<script lang="ts">
  // Tongue-in-cheek "steps" shown on the second line while something loads.
  const DEFAULT_STEPS = [
    "Flabbering the database…",
    "Finishing the blabbing…",
    "Reticulating splines…",
    "Untangling the widgets…",
    "Greasing the cogwheels…",
    "Polishing the pixels…",
    "Aligning the flux capacitors…",
    "Marinating the schemas…",
    "Convincing the electrons…",
    "Herding the kanban cats…",
    "Whittling the swimlanes…",
    "Calibrating the vibes…",
    "Summoning the backlog gnomes…",
    "Defragmenting the coffee…",
    "Bribing the scheduler…",
    "Untwisting the dependencies…",
    "Fluffing the epics…",
    "Warming up the hamsters…",
    "Buttering the breadcrumbs…",
    "Negotiating with the mutex…",
  ];

  // `label` is the prominent top line; `substeps` (defaulting to the pool above)
  // is rotated on the quieter second line at a random 1–3s cadence. Pass
  // `substeps={[]}` to show just the label.
  let {
    label = "",
    substeps = DEFAULT_STEPS,
  }: { label?: string; substeps?: string[] } = $props();

  let current = $state("");
  let timer: ReturnType<typeof setTimeout> | undefined;

  function pick(): string {
    return substeps[Math.floor(Math.random() * substeps.length)];
  }

  function scheduleNext() {
    // Switch at a random interval between 1 and 3 seconds.
    timer = setTimeout(
      () => {
        current = pick();
        scheduleNext();
      },
      1000 + Math.random() * 2000,
    );
  }

  $effect(() => {
    if (substeps.length > 0) {
      current = pick();
      scheduleNext();
    }
    return () => clearTimeout(timer);
  });
</script>

<div class="spinner-wrap">
  <div class="ring" aria-hidden="true"></div>
  {#if label}
    <p class="label">{label}</p>
  {/if}
  {#if substeps.length > 0}
    <p class="substep">{current}</p>
  {/if}
</div>

<style>
  .spinner-wrap {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 0.6rem;
    text-align: center;
  }
  .ring {
    width: 40px;
    height: 40px;
    border: 4px solid #e2e8f0;
    border-top-color: #4f46e5;
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
    margin-bottom: 0.3rem;
  }
  .label {
    margin: 0;
    color: #1e293b;
    font-size: 1.1rem;
    font-weight: 600;
  }
  .substep {
    margin: 0;
    min-height: 1.2em;
    color: #94a3b8;
    font-size: 0.85rem;
  }
  @keyframes spin {
    to {
      transform: rotate(360deg);
    }
  }
  @media (prefers-reduced-motion: reduce) {
    .ring {
      animation-duration: 2s;
    }
  }
</style>
