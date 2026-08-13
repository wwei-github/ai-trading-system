// API 模块统一出口
export { accountApi } from './accounts';
export { tradeApi } from './trades';
export { statisticsApi } from './statistics';

// 以下模块待后续迭代实现
// export { aiApi } from './ai';
// export { bookApi } from './books';
// export { coinApi } from './coins';
// export { strategyApi } from './strategies';
// export { systemApi } from './system';

export { default as request } from './request';
