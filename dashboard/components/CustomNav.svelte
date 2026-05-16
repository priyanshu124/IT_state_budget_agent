<script>
    import { page } from '$app/stores';

    const nav = [
        {
            label: 'Home',
            href: '/',
            icon: '🏠',
        },
        {
            label: 'State Budget',
            href: '/state-budget',
            icon: '🏛️',
            children: [
                { label: 'Agency Breakdown', href: '/state-budget/agencies' }
            ]
        },
        {
            label: 'Technology',
            href: '/technology',
            icon: '💻',
            children: [
                { label: 'Agency Breakdown', href: '/technology/agencies' }
            ]
        },
        {
            label: 'MITDPs',
            href: '/mitdps',
            icon: '🚀',
            children: [
                { label: 'Project Details', href: '/mitdps/project-details' }
            ]
        },
        {
            label: 'Variance Analysis',
            href: '/variance-analysis',
            icon: '📊',
        },
        {
            label: 'Anomaly Detection',
            href: '/anomaly-detection',
            icon: '🔍',
        },
    ];

    $: currentPath = $page.url.pathname;

    function isActive(href) {
        if (href === '/') return currentPath === '/';
        return currentPath === href || currentPath.startsWith(href + '/');
    }

    function isSectionActive(item) {
        if (isActive(item.href)) return true;
        if (item.children) return item.children.some(c => isActive(c.href));
        return false;
    }
</script>

<nav class="custom-nav">
    {#each nav as item}
        <div class="nav-section" class:section-active={isSectionActive(item)}>
            <a href={item.href} class="nav-parent" class:active={isActive(item.href)}>
                <span class="nav-icon">{item.icon}</span>
                <span class="nav-label">{item.label}</span>
                {#if item.children}
                    <span class="nav-chevron" class:open={isSectionActive(item)}>›</span>
                {/if}
            </a>
            {#if item.children && isSectionActive(item)}
                <div class="nav-children">
                    {#each item.children as child}
                        <a href={child.href} class="nav-child" class:active={isActive(child.href)}>
                            <span class="nav-child-indicator">↳</span>
                            {child.label}
                        </a>
                    {/each}
                </div>
            {/if}
        </div>
    {/each}
</nav>

<style>
    .custom-nav {
        display: flex;
        flex-direction: column;
        gap: 2px;
        padding: 12px 8px;
        font-family: 'IBM Plex Sans', sans-serif;
    }

    .nav-parent {
        display: flex;
        align-items: center;
        gap: 8px;
        padding: 8px 12px;
        border-radius: 8px;
        text-decoration: none;
        color: #3a1f5a;
        font-size: 0.875rem;
        font-weight: 500;
        transition: background 0.15s, color 0.15s;
    }

    .nav-parent:hover {
        background: rgba(128, 44, 215, 0.10);
        color: #6321a5;
    }

    .nav-parent.active {
        background: #802cd7;
        color: #ffffff;
        font-weight: 600;
        border-left: 3px solid #b376f6;
    }

    .section-active > .nav-parent:not(.active) {
        background: rgba(128, 44, 215, 0.07);
        color: #6321a5;
        font-weight: 600;
    }

    .nav-icon {
        font-size: 0.9rem;
        width: 18px;
        text-align: center;
        flex-shrink: 0;
    }

    .nav-label { flex: 1; }

    .nav-chevron {
        font-size: 1rem;
        color: #b376f6;
        font-weight: 700;
        transition: transform 0.15s;
        display: inline-block;
    }

    .nav-chevron.open {
        transform: rotate(90deg);
    }

    .nav-children {
        display: flex;
        flex-direction: column;
        gap: 1px;
        padding: 2px 0 4px 0;
        border-left: 2px solid #c9a8f0;
        margin: 2px 0 4px 22px;
    }

    .nav-child {
        display: flex;
        align-items: center;
        gap: 6px;
        padding: 6px 12px;
        border-radius: 6px;
        text-decoration: none;
        color: #6B7280;
        font-size: 0.82rem;
        font-weight: 400;
        transition: background 0.15s, color 0.15s;
    }

    .nav-child:hover {
        background: rgba(128, 44, 215, 0.08);
        color: #6321a5;
    }

    .nav-child.active {
        color: #802cd7;
        font-weight: 600;
        background: rgba(128, 44, 215, 0.08);
    }

    .nav-child-indicator {
        font-size: 0.75rem;
        color: #b376f6;
        flex-shrink: 0;
    }
</style>