import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'dashboard', component: () => import('../views/DashboardView.vue') },
    { path: '/assets', name: 'assets', component: () => import('../views/AssetsView.vue') },
    { path: '/assets/:id', name: 'asset-detail', component: () => import('../views/AssetDetailView.vue') },
    { path: '/anomalies', name: 'anomalies', component: () => import('../views/AnomaliesView.vue') },
    { path: '/alerts', name: 'alerts', component: () => import('../views/AlertsView.vue') },
    { path: '/recommendations', name: 'recommendations', component: () => import('../views/RecommendationsView.vue') },
    { path: '/portfolio', name: 'portfolio', component: () => import('../views/PortfolioView.vue') },
    { path: '/performance', name: 'performance', component: () => import('../views/PerformanceView.vue') },
    { path: '/strategy', name: 'strategy', component: () => import('../views/StrategyView.vue') },
    { path: '/strategy-builder', name: 'strategy-builder', component: () => import('../views/StrategyBuilderView.vue') },
    { path: '/backtest', name: 'backtest', component: () => import('../views/BacktestView.vue') },
    { path: '/watchlists', name: 'watchlists', component: () => import('../views/WatchlistsView.vue') },
    { path: '/reports', name: 'reports', component: () => import('../views/ReportsView.vue') },
    { path: '/reports/:id', name: 'report-detail', component: () => import('../views/ReportDetailView.vue') },
    { path: '/ingestion', name: 'ingestion', component: () => import('../views/IngestionView.vue') },
    { path: '/marketplace', name: 'Marketplace', component: () => import('../views/MarketplaceView.vue') },
  ],
})

export default router
