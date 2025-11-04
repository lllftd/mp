package com.jxwq.utils.date;

import com.jxwq.utils.StringUtils;
import org.apache.commons.lang3.time.DateFormatUtils;

import java.lang.management.ManagementFactory;
import java.text.DateFormat;
import java.text.ParseException;
import java.text.SimpleDateFormat;
import java.time.*;
import java.util.*;
import java.util.stream.Collectors;

/**
 * 时间工具类
 *
 * @author ruoyi
 */
public class DateUtils extends org.apache.commons.lang3.time.DateUtils {
    public static String YYYY = "yyyy";

    public static String YYYY_MM = "yyyy-MM";

    public static String YYYYMMDD = "yyyyMMdd";

    public static String YYYY_MM_DD = "yyyy-MM-dd";

    public static String YYYYMMDDHHMMSS = "yyyyMMddHHmmss";

    public static String YYYY_MM_DD_HH_MM_SS = "yyyy-MM-dd HH:mm:ss";

    public static final String FORMAT_TIME = "HH:mm:ss";

    private static String[] parsePatterns = {
            "yyyy-MM-dd", "yyyy-MM-dd HH:mm:ss", "yyyy-MM-dd HH:mm", "yyyy-MM",
            "yyyy/MM/dd", "yyyy/MM/dd HH:mm:ss", "yyyy/MM/dd HH:mm", "yyyy/MM",
            "yyyy.MM.dd", "yyyy.MM.dd HH:mm:ss", "yyyy.MM.dd HH:mm", "yyyy.MM", "yyyy-MM-dd HH:mm:ss.SSS"};

    /**
     * 获取当前Date型日期
     *
     * @return Date() 当前日期
     */
    public static Date getNowDate() {
        return new Date();
    }

    /**
     * 获取当前日期, 默认格式为yyyy-MM-dd
     *
     * @return String
     */
    public static String getDate() {
        return dateTimeNow(YYYY_MM_DD);
    }

    public static final String getTime() {
        return dateTimeNow(YYYY_MM_DD_HH_MM_SS);
    }

    public static final String dateTimeNow() {
        return dateTimeNow(YYYYMMDDHHMMSS);
    }

    public static final String dateTimeNow(final String format) {
        return parseDateToStr(format, new Date());
    }

    public static final String dateTime(final Date date) {
        return parseDateToStr(YYYY_MM_DD, date);
    }

    public static final String dateMonth(final Date date) {
        return parseDateToStr(YYYY_MM, date);
    }

    public static final String parseDateToStr(final String format, final Date date) {
        return new SimpleDateFormat(format).format(date);
    }

    public static final Date dateTime(final String format, final String ts) {
        try {
            return new SimpleDateFormat(format).parse(ts);
        } catch (ParseException e) {
            throw new RuntimeException(e);
        }
    }

    // date to localDateTime
    public static LocalDateTime UDateToLocalDateTime(Date date) {
        Instant instant = date.toInstant();
        ZoneId zone = ZoneId.systemDefault();
        return LocalDateTime.ofInstant(instant, zone);
    }

    /**
     * 日期路径 即年/月/日 如2018/08/08
     */
    public static final String datePath() {
        Date now = new Date();
        return DateFormatUtils.format(now, "yyyy/MM/dd");
    }

    /**
     * 日期路径 即年/月/日 如20180808
     */
    public static final String dateTime() {
        Date now = new Date();
        return DateFormatUtils.format(now, "yyyyMMdd");
    }

    /**
     * 日期型字符串转化为日期 格式
     */
    public static Date parseDate(Object str) {
        if (str == null) {
            return null;
        }
        try {
            return parseDate(str.toString(), parsePatterns);
        } catch (ParseException e) {
            return null;
        }
    }

    /**
     * 获取服务器启动时间
     */
    public static Date getServerStartDate() {
        long time = ManagementFactory.getRuntimeMXBean().getStartTime();
        return new Date(time);
    }

    /**
     * 计算两个时间差
     */
    public static String getDatePoor(Date endDate, Date nowDate) {
        long nd = 1000 * 24 * 60 * 60;
        long nh = 1000 * 60 * 60;
        long nm = 1000 * 60;
        // long ns = 1000;
        // 获得两个时间的毫秒时间差异
        long diff = endDate.getTime() - nowDate.getTime();
        // 计算差多少天
        long day = diff / nd;
        // 计算差多少小时
        long hour = diff % nd / nh;
        // 计算差多少分钟
        long min = diff % nd % nh / nm;
        // 计算差多少秒//输出结果
        // long sec = diff % nd % nh % nm / ns;
        return day + "天" + hour + "小时" + min + "分钟";
    }

    /**
     * 计算两个时间相差天数
     */
    public static Long getDaysDiff(Date start, Date end) {
        if (start == null || end == null) {
            return 0L;
        }
        long day = 1000 * 24 * 60 * 60;
        // 获得两个时间的毫秒时间差异
        long diff = end.getTime() - start.getTime();
        // 计算差多少天
        return diff / day;
    }

    /**
     * 计算相差月份
     *
     * @param start
     * @param end
     * @return
     */
    public static long getMonthDiff(Date end, Date start) {
        Calendar c1 = Calendar.getInstance();
        Calendar c2 = Calendar.getInstance();
        c1.setTime(end);
        c2.setTime(start);
        int year1 = c1.get(Calendar.YEAR);
        int year2 = c2.get(Calendar.YEAR);
        int month1 = c1.get(Calendar.MONTH);
        int month2 = c2.get(Calendar.MONTH);
        int day1 = c1.get(Calendar.DAY_OF_MONTH);
        int day2 = c2.get(Calendar.DAY_OF_MONTH);
        // 获取年的差值?
        int yearInterval = year1 - year2;
        // 如果 d1的 月-日 小于 d2的 月-日 那么 yearInterval-- 这样就得到了相差的年数
        if (month1 < month2 || month1 == month2 && day1 < day2) {
            yearInterval--;
        }
        // 获取月数差值
        int monthInterval = (month1 + 12) - month2;
        if (day1 < day2) {
            monthInterval--;
        }
        monthInterval %= 12;
        int monthsDiff = Math.abs(yearInterval * 12 + monthInterval);
        return monthsDiff;
    }

    /**
     * 计算两个日期年月日差
     */
    public static Map<String, Integer> getDatePoor2(String startDate, String endDate) {
        List<Integer> startDateCollect = Arrays.stream(startDate.split("-")).map(str -> Integer.parseInt(str)).collect(Collectors.toList());
        List<Integer> endDateCollect = Arrays.stream(endDate.split("-")).map(str -> Integer.parseInt(str)).collect(Collectors.toList());
        // 2010年10月12日，month从0开始  （6表明的是5月）
        Calendar start = new GregorianCalendar(startDateCollect.get(0), startDateCollect.get(1) - 1, startDateCollect.get(2));
        // 2010年10月12日，month从0开始
        Calendar end = new GregorianCalendar(endDateCollect.get(0), endDateCollect.get(1) - 1, endDateCollect.get(2));
        int day = end.get(Calendar.DAY_OF_MONTH) - start.get(Calendar.DAY_OF_MONTH);
        int month = end.get(Calendar.MONTH) - start.get(Calendar.MONTH);
        int year = end.get(Calendar.YEAR) - start.get(Calendar.YEAR);
        // 按照减法原理，先day相减，不够向month借；而后month相减，不够向year借；最后year相减。
        if (day < 0) {
            month -= 1;
            end.add(Calendar.MONTH, -1);// 获得上一个月，用来获得上个月的天数。
            day = day + end.getActualMaximum(Calendar.DAY_OF_MONTH);
        }
        if (month < 0) {
            month = (month + 12) % 12;
            year--;
        }
        Map<String, Integer> map = new HashMap<>();
        map.put("year", year);
        map.put("month", month);
        map.put("day", day);
        return map;
    }

    /**
     * 将指定字符串类型转换为日期类型 转换后格式为:yyyy-MM-dd
     *
     * @param str
     * @return
     */
    public static Date parse(String str) {
        if (StringUtils.isEmpty(str)) {
            return null;
        }
        try {
            return new SimpleDateFormat(YYYY_MM_DD).parse(str);
        } catch (ParseException e) {
            e.printStackTrace();
        }
        return null;
    }

    /**
     * 将字符串类型转换为日期类型
     *
     * @param str    <要转换的字符串>
     * @param format <转换后的格式>
     * @return
     */
    public static Date parse(String str, String format) {
        if (StringUtils.isEmpty(str)) {
            return null;
        }
        try {
            SimpleDateFormat sdf = new SimpleDateFormat(format);

            return sdf.parse(str);
        } catch (ParseException e) {
            e.printStackTrace();
        }
        return null;
    }

    /**
     * 将毫秒数转化为date格式
     *
     * @param time
     * @return
     */
    public static Date parse(Long time) {
        if (time == null) {
            return null;
        } else {
            Calendar cal = Calendar.getInstance();
            cal.setTimeInMillis(time);
            return cal.getTime();
        }
    }

    /**
     * 获取过去第几天的日期
     *
     * @param past
     * @return
     */
    public static String getPastDate(int past) {
        Calendar calendar = Calendar.getInstance();
        calendar.set(Calendar.DAY_OF_YEAR, calendar.get(Calendar.DAY_OF_YEAR) - past);
        Date today = calendar.getTime();
        String result = new SimpleDateFormat("yyyyMMdd").format(today);
        return result;
    }

    /**
     * 返回当前时间,格式为HH:mm:ss
     *
     * @return
     */
    public static String getCurrentTime() {
        return new SimpleDateFormat(FORMAT_TIME).format(new Date());
    }

    public static String getStringTime(String format, Date date) {
        return new SimpleDateFormat(format).format(date);
    }

    /**
     * 给指定时间增加天数
     *
     * @param date
     * @param count
     * @return
     */
    public static Date addDay(Date date, int count) {
        return new Date(date.getTime() + 86400000L * count);
    }

    public static String dealDate(String oldDateStr) throws ParseException {
        DateFormat df = new SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss");
        Date date = df.parse(oldDateStr);
        SimpleDateFormat df1 = new SimpleDateFormat("EEE MMM dd HH:mm:ss Z yyyy", Locale.UK);
        Date date1 = df1.parse(date.toString());
        DateFormat df2 = new SimpleDateFormat("yyyy-MM-dd HH:mm:ss");
        return df2.format(date1);
    }

    // 计算两个时间相差秒数 传入的是字符串格式的毫秒
    public static int calLastedTime(String startDate, String endDate) {
        long a = Long.parseLong(endDate);
        long b = Long.parseLong(startDate);
        return (int) ((a - b) / 1000);
    }

    /**
     * 获取当前时间到凌晨12点的秒数
     *
     * @return
     */
    public static Long getSecondsNextEarlyMorning() {
        Calendar cal = Calendar.getInstance();
        cal.add(Calendar.DAY_OF_YEAR, 1);
        cal.set(Calendar.HOUR_OF_DAY, 0);
        cal.set(Calendar.SECOND, 0);
        cal.set(Calendar.MINUTE, 0);
        cal.set(Calendar.MILLISECOND, 0);
        return (cal.getTimeInMillis() - System.currentTimeMillis()) / 1000;
    }

    /**
     * 返回当前日期,格式为yyyy-MM-dd
     *
     * @return
     */
    public static final String getCurrentDateStr() {
        return new SimpleDateFormat("yyyy-MM-dd").format(new Date());
    }

    /**
     * 计算两个时间差 （秒）
     *
     * @param startDate
     * @param endDate
     * @return
     */
    public static int getTimeInterval(Date startDate, Date endDate) {
        long a = endDate.getTime();
        long b = startDate.getTime();
        int c = (int) ((a - b) / 1000L);
        return c;
    }

    public static String getFormatTime() {
        return new SimpleDateFormat(YYYY_MM_DD_HH_MM_SS).format(new Date());
    }

    /**
     * 增加 LocalDateTime ==> Date
     */
    public static Date toDate(LocalDateTime temporalAccessor) {
        ZonedDateTime zdt = temporalAccessor.atZone(ZoneId.systemDefault());
        return Date.from(zdt.toInstant());
    }

    /**
     * 增加 LocalDate ==> Date
     */
    public static Date toDate(LocalDate temporalAccessor) {
        LocalDateTime localDateTime = LocalDateTime.of(temporalAccessor, LocalTime.of(0, 0, 0));
        ZonedDateTime zdt = localDateTime.atZone(ZoneId.systemDefault());
        return Date.from(zdt.toInstant());
    }

    /**
     * 判断当前时间是否在[startTime, endTime]区间，注意时间格式要一致
     *
     * @param nowTime   当前时间
     * @param startTime 开始时间
     * @param endTime   结束时间
     * @return
     */
    public static boolean isEffectiveDate(Date nowTime, Date startTime, Date endTime) {
        if (nowTime.getTime() == startTime.getTime()
                || nowTime.getTime() == endTime.getTime()) {
            return true;
        }

        Calendar date = Calendar.getInstance();
        date.setTime(nowTime);

        Calendar begin = Calendar.getInstance();
        begin.setTime(startTime);

        Calendar end = Calendar.getInstance();
        end.setTime(endTime);

        if (date.after(begin) && date.before(end)) {
            return true;
        } else {
            return false;
        }
    }

    /**
     * 计算两个时间差--分钟
     */
    public static long getDatePoorMin(Date endDate, Date nowDate) {
        long nd = 1000 * 24 * 60 * 60;
        long nh = 1000 * 60 * 60;
        long nm = 1000 * 60;
        // long ns = 1000;
        // 获得两个时间的毫秒时间差异
        long diff = endDate.getTime() - nowDate.getTime();
        // 计算差多少分钟
        long min = diff % nd % nh / nm;
        // 计算差多少秒//输出结果
        // long sec = diff % nd % nh % nm / ns;
        return min;
    }

    // 时间戳专程date
    public static Date timeStamp2Date(String seconds, String format) {
        if (format == null || format.isEmpty()) {
            format = "yyyy-MM-dd HH:mm:ss";
        }
        SimpleDateFormat sdf = new SimpleDateFormat(format);
        return new Date(Long.valueOf(seconds));
    }
}
