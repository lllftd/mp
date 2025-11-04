package com.jxwq.utils;

import java.io.*;
import java.security.MessageDigest;
import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.List;

/**
 * @author LZK
 * @version 1.0
 * @date 2021/6/3 16:31
 */
public class CommonUtils {

    /**
     * Object转Double
     *
     * @param value
     * @return
     */
    public static Double object2Double(Object value) {
        double int_val = 0.0D;

        try {
            int_val = Double.parseDouble(String.valueOf(value));
        } catch (Exception var4) {
        }

        return int_val;
    }


    /**
     * Object转Long
     *
     * @param value
     * @return
     */
    public static Long object2Long(Object value) {
        long int_val = 0;
        try {
            int_val = Long.parseLong(String.valueOf(value));
        } catch (Exception e) {

        }
        return int_val;
    }

    /**
     * Object转Integer
     *
     * @param value
     * @return
     */
    public static Integer object2Int(Object value) {
        int int_val = 0;

        try {
            int_val = (int) Double.parseDouble(String.valueOf(value));
        } catch (Exception var3) {
        }

        return int_val;
    }

    public static Double string2Double(String value) {
        double int_val = 0;
        try {
            int_val = Double.parseDouble(value);
        } catch (Exception e) {

        }
        return int_val;
    }

    /**
     * Object转String
     *
     * @param value
     * @return
     */
    public static String stringValue(Object value) {
        return value == null ? null : String.valueOf(value);
    }


    /**
     * String转Integer
     *
     * @param value
     * @return
     */
    public static Integer string2Int(String value) {
        int int_val = 0;
        try {
            int_val = Integer.parseInt(value);
        } catch (Exception e) {

        }
        return int_val;
    }

    public static String DateToStr(Date rq, String format) {
        SimpleDateFormat sdf = new SimpleDateFormat(format);
        if (rq == null)
            rq = new Date();
        return sdf.format(rq);
    }

    /**
     * MD5
     *
     * @param src
     * @return
     */
    public static String getMD5(String src) {
        char hexDigits[] = {'0', '1', '2', '3', '4', '5', '6', '7', '8', '9', 'A', 'B', 'C', 'D', 'E', 'F'};
        try {
            if ("".equals(src)) {
                throw new Exception();
            }
            byte[] btInput = src.getBytes();
            MessageDigest mdInst = MessageDigest.getInstance("MD5");
            mdInst.update(btInput);
            byte[] md = mdInst.digest();
            int j = md.length;
            char str[] = new char[j * 2];
            int k = 0;
            for (int i = 0; i < j; i++) {
                byte byte0 = md[i];
                str[k++] = hexDigits[byte0 >>> 4 & 0xf];
                str[k++] = hexDigits[byte0 & 0xf];
            }
            return new String(str);
        } catch (Exception e) {
            e.printStackTrace();
            return null;
        }
    }

    /**
     * 深拷贝集合对象
     */
    public static <T> List<T> deepCopy(List<T> src) throws IOException, ClassNotFoundException {
        ByteArrayOutputStream byteOut = new ByteArrayOutputStream();
        ObjectOutputStream out = new ObjectOutputStream(byteOut);
        out.writeObject(src);

        ByteArrayInputStream byteIn = new ByteArrayInputStream(byteOut.toByteArray());
        ObjectInputStream in = new ObjectInputStream(byteIn);
        @SuppressWarnings("unchecked")
        List<T> dest = (List<T>) in.readObject();
        return dest;
    }
}
