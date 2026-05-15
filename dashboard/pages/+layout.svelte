<script>
    import '@evidence-dev/tailwind/fonts.css';
    import '../app.css';
    import { onMount } from 'svelte';
    import { page } from '$app/stores';
    import { EvidenceDefaultLayout } from '@evidence-dev/core-components';
    import { showQueries } from '@evidence-dev/component-utilities/stores';
    export let data;

    onMount(() => {
        showQueries.set(false);
    });

    let chatOpen = false;
    $: pageSlug = $page.url.pathname.replace(/\//g, '-').replace(/^-/, '') || 'home';
    $: chatSrc = `http://localhost:8501?page=${pageSlug}&embed=true`;
</script>

<svelte:head>
    <link rel="stylesheet" href="/custom.css"/>
    <link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@300;400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500;700&display=swap" rel="stylesheet">
</svelte:head>

<EvidenceDefaultLayout
    {data}
    title="MBTSA"
    logo="/maryland-logo.png"
    homePageName="Budget Office"
    neverShowQueries={true}
    maxWidth="1200px"
>
    <div slot="header">
        <div style="background:#ede5f8; height:3px; width:100%; border-bottom:2px solid #c9a8f0;"></div>
    </div>
    <slot slot="content" />
    <div slot="footer">
        <p style="font-size: 0.7rem; color: #6B7280; text-align: center; padding: 16px 0; border-top: 1px solid #e2d9f3; margin-top: 32px; font-family:'IBM Plex Sans',sans-serif;">
            State of Maryland · Department of Budget & Management · Data: FY2020–FY2027 · TBM v5.0.1
        </p>
    </div>
</EvidenceDefaultLayout>

<!-- Floating chat button -->
<button
    class="chat-fab"
    on:click={() => chatOpen = !chatOpen}
    aria-label="Open budget assistant"
>
    {#if chatOpen}
        <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24"
             fill="none" stroke="currentColor" stroke-width="2.5"
             stroke-linecap="round" stroke-linejoin="round">
            <line x1="18" y1="6" x2="6" y2="18"/>
            <line x1="6" y1="6" x2="18" y2="18"/>
        </svg>
    {:else}
        <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24"
             fill="none" stroke="currentColor" stroke-width="2"
             stroke-linecap="round" stroke-linejoin="round">
            <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
        </svg>
        <span>Ask AI</span>
    {/if}
</button>

<!-- Slide-in chat panel -->
{#if chatOpen}
    <div class="chat-panel" role="complementary" aria-label="Budget assistant">
        <div class="chat-panel-header">
            <span class="chat-panel-title">
                <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24"
                     fill="none" stroke="currentColor" stroke-width="2"
                     stroke-linecap="round" stroke-linejoin="round"
                     style="margin-right:6px;vertical-align:-1px">
                    <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
                </svg>
                Budget Assistant
            </span>
            <span class="chat-panel-page">{pageSlug.replace(/-/g, ' ')}</span>
        </div>
        <iframe src={chatSrc} title="Budget Assistant" frameborder="0" />
    </div>
{/if}

<style>
    :global(h1), :global(h2), :global(h3), :global(h4) {
        font-family: 'Montserrat', sans-serif !important;
        color: #231F20 !important;
    }

    :global(div.inline-block.font-sans.pt-2.pb-3.pl-0.mr-3.items-center.align-top) {
        background: transparent !important;
        border: 1px solid #E8E0D8 !important;
        border-left: 4px solid #C8122C !important;
        border-radius: 12px !important;
        box-shadow: 0 2px 8px rgba(35, 31, 32, 0.05) !important;
        padding: 14px 16px !important;
        margin-right: 0 !important;
        min-width: 170px !important;
    }

    :global(div.inline-block.font-sans.pt-2.pb-3.pl-0.mr-3.items-center.align-top:nth-of-type(4n + 1)) { border-left-color: #C8122C !important; }
    :global(div.inline-block.font-sans.pt-2.pb-3.pl-0.mr-3.items-center.align-top:nth-of-type(4n + 2)) { border-left-color: #FFC838 !important; }
    :global(div.inline-block.font-sans.pt-2.pb-3.pl-0.mr-3.items-center.align-top:nth-of-type(4n + 3)) { border-left-color: #3B7DD8 !important; }
    :global(div.inline-block.font-sans.pt-2.pb-3.pl-0.mr-3.items-center.align-top:nth-of-type(4n))     { border-left-color: #2EAD6B !important; }

    :global(div.inline-block.font-sans.pt-2.pb-3.pl-0.mr-3.items-center.align-top > p.text-sm) {
        color: #6B5F57 !important;
        font-size: 0.78rem !important;
        font-weight: 600 !important;
        letter-spacing: 0.02em !important;
        text-transform: uppercase !important;
        margin-bottom: 6px !important;
    }

    :global(div.inline-block.font-sans.pt-2.pb-3.pl-0.mr-3.items-center.align-top > div.relative.text-xl) {
        color: #231F20 !important;
        font-size: 1.75rem !important;
        font-weight: 700 !important;
        line-height: 1.15 !important;
    }

    :global(blockquote) {
        border-left: 4px solid #C8122C !important;
        background: #F5F0EB !important;
        padding: 14px 18px !important;
        border-radius: 0 6px 6px 0 !important;
        margin: 16px 0 !important;
    }

    :global(th) { border-bottom: 2px solid #C8122C !important; }

    /* Chat FAB */
    .chat-fab {
        position: fixed;
        bottom: 28px;
        right: 28px;
        z-index: 9999;
        display: flex;
        align-items: center;
        gap: 7px;
        background: #C8122C;
        color: #fff;
        border: none;
        border-radius: 50px;
        padding: 12px 18px 12px 14px;
        cursor: pointer;
        box-shadow: 0 4px 18px rgba(200,18,44,0.4);
        transition: background 0.15s, box-shadow 0.15s, transform 0.1s;
        font-family: 'IBM Plex Sans', sans-serif;
        font-size: 0.88rem;
        font-weight: 600;
        letter-spacing: 0.01em;
    }
    .chat-fab:hover {
        background: #a80e24;
        box-shadow: 0 6px 24px rgba(200,18,44,0.5);
        transform: translateY(-1px);
    }
    .chat-fab:active { transform: translateY(0); }

    /* Chat panel */
    .chat-panel {
        position: fixed;
        bottom: 88px;
        right: 28px;
        z-index: 9998;
        width: 390px;
        height: 620px;
        background: #F8F6F2;
        border-radius: 14px;
        box-shadow: 0 8px 40px rgba(0,0,0,0.2);
        display: flex;
        flex-direction: column;
        overflow: hidden;
        border: 1px solid #E5E7EB;
        animation: slideUp 0.18s ease-out;
    }

    @keyframes slideUp {
        from { opacity: 0; transform: translateY(12px) scale(0.98); }
        to   { opacity: 1; transform: translateY(0) scale(1); }
    }

    .chat-panel-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 11px 16px;
        background: #FFFFFF;
        border-bottom: 1px solid #E5E7EB;
        flex-shrink: 0;
    }

    .chat-panel-title {
        font-family: 'IBM Plex Sans', sans-serif;
        font-size: 0.85rem;
        font-weight: 600;
        color: #111827;
    }

    .chat-panel-page {
        font-family: 'IBM Plex Sans', sans-serif;
        font-size: 0.7rem;
        color: #6B7280;
        text-transform: capitalize;
        background: #F3F4F6;
        padding: 2px 8px;
        border-radius: 10px;
        border: 1px solid #E5E7EB;
    }

    .chat-panel iframe {
        flex: 1;
        width: 100%;
        border: none;
    }

    @media (max-width: 500px) {
        .chat-panel {
            bottom: 0;
            right: 0;
            width: 100vw;
            height: 80vh;
            border-radius: 16px 16px 0 0;
        }
        .chat-fab { bottom: 20px; right: 20px; }
    }
</style>