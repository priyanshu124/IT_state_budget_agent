<script>
    import '@evidence-dev/tailwind/fonts.css';
    import '../app.css';
    import { onMount } from 'svelte';
    import { EvidenceDefaultLayout } from '@evidence-dev/core-components';
    import { showQueries } from '@evidence-dev/component-utilities/stores';
    export let data;

    onMount(() => {
        // Hide inline query inspector panels globally in the dashboard.
        showQueries.set(false);
    });
</script>

<svelte:head>
    <link rel="stylesheet" href="/custom.css"/>
    <link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@300;400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500;700&display=swap" rel="stylesheet">
</svelte:head>

<EvidenceDefaultLayout
    {data}
    title="MBTSA"
    logo="/maryland-logo.png"
    homePageName="Home"
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

<style>
    :global(h1), :global(h2), :global(h3), :global(h4) {
        font-family: 'Montserrat', sans-serif !important;
        color: #231F20 !important;
    }

    /* Global KPI card styling for all Evidence BigValue components */
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

    /* Alternate KPI accent colors for clearer card separation */
    :global(div.inline-block.font-sans.pt-2.pb-3.pl-0.mr-3.items-center.align-top:nth-of-type(4n + 1)) {
        border-left-color: #C8122C !important;
    }

    :global(div.inline-block.font-sans.pt-2.pb-3.pl-0.mr-3.items-center.align-top:nth-of-type(4n + 2)) {
        border-left-color: #FFC838 !important;
    }

    :global(div.inline-block.font-sans.pt-2.pb-3.pl-0.mr-3.items-center.align-top:nth-of-type(4n + 3)) {
        border-left-color: #3B7DD8 !important;
    }

    :global(div.inline-block.font-sans.pt-2.pb-3.pl-0.mr-3.items-center.align-top:nth-of-type(4n)) {
        border-left-color: #2EAD6B !important;
    }

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

    :global(th) {
        border-bottom: 2px solid #C8122C !important;
    }
</style>