// dateFormatter.js

/**
 * 格式化时间戳为指定格式的日期字符串
 * @param {number} timestamp - 时间戳（秒）
 * @param {string} format - 输出的格式，默认 "YYYY-MM-DD HH:mm:ss"
 * @returns {string} 格式化后的日期字符串
 */
const formatDate = (timestamp, format = 'YYYY-MM-DD HH:mm:ss') => {
    const date = new Date(timestamp * 1000);
    
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0'); // 月份从0开始
    const day = String(date.getDate()).padStart(2, '0');
    const hours = String(date.getHours()).padStart(2, '0');
    const minutes = String(date.getMinutes()).padStart(2, '0');
    const seconds = String(date.getSeconds()).padStart(2, '0');

    // 根据格式构建返回的字符串
    return format
        .replace('YYYY', year)
        .replace('MM', month)
        .replace('DD', day)
        .replace('HH', hours)
        .replace('mm', minutes)
        .replace('ss', seconds);
};

// 导出函数
export { formatDate };