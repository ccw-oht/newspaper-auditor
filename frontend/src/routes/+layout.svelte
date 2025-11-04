<script lang="ts">
  import { page } from '$app/stores';

  const navLinks = [
    { href: '/papers', label: 'Papers' },
    { href: '/imports', label: 'Imports' }
  ];
</script>

<svelte:head>
  <title>Newspaper Audit Dashboard</title>
  <meta name="viewport" content="width=device-width, initial-scale=1" />
</svelte:head>

<div class="app-shell">
  <header class="app-header">
    <div class="branding">
      <img src="/audit.png" alt="Newspaper Audit logo" class="logo" />
      <h1>Newspaper Audit Dashboard</h1>
    </div>
    <nav>
      {#each navLinks as link}
        <a
          href={link.href}
          class:active={$page.url.pathname.startsWith(link.href)}
        >
          {link.label}
        </a>
      {/each}
    </nav>
  </header>
  <main>
    <slot />
  </main>
</div>

<style>
  :global(body) {
    margin: 0;
    font-family: 'Inter', system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    background-color: #f3f4f6;
    color: #111827;
  }

  .app-shell {
    min-height: 100vh;
    display: flex;
    flex-direction: column;
  }

  .app-header {
    background-color: #111827;
    color: white;
    padding: 1.5rem 2rem;
    display: flex;
    align-items: center;
    justify-content: space-between;
  }

  .branding {
    display: flex;
    align-items: center;
    gap: 0.75rem;
  }

  .logo {
    height: 2.5rem;
    width: auto;
  }

  nav a {
    color: white;
    margin-left: 1rem;
    text-decoration: none;
    font-weight: 600;
  }

  nav a:hover {
    text-decoration: underline;
  }

  main {
    flex: 1;
    padding: 2rem;
  }
</style>
