<script lang="ts">
  let { label = "" }: { label?: string } = $props();
</script>

<div class="spinner-wrap">
  <div class="ring" aria-hidden="true"></div>
  {#if label}
    <p class="label">{label}</p>
  {/if}
</div>

<style>
  .spinner-wrap {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 0.9rem;
  }
  .ring {
    width: 40px;
    height: 40px;
    border: 4px solid #e2e8f0;
    border-top-color: #4f46e5;
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
  }
  .label {
    margin: 0;
    color: #475569;
    font-size: 0.9rem;
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
