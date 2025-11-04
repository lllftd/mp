package com.jxwq.result;

import com.jxwq.constant.HttpStatus;
import lombok.Data;

import java.io.Serializable;

/**
 * 后端统一返回结果
 *
 * @param <T>
 */
@Data
public class Result<T> implements Serializable {

    // 编码：200成功，500和其它数字为失败
    private Integer code;

    // 错误信息 错误才会有
    private String msg;

    // 数据
    private T data;

    // 成功的返回
    public static <T> Result<T> success() {
        Result<T> result = new Result<T>();
        result.code = 1;
        return result;
    }

    // 失败的返回
    public static <T> Result<T> error(String msg) {
        Result<T> result = new Result<T>();
        result.code = HttpStatus.ERROR;
        result.msg = msg;
        return result;
    }

    // 带数据的成功返回
    public static <T> Result<T> success(T object) {
        Result<T> result = new Result<T>();
        result.data = object;
        result.code = HttpStatus.SUCCESS;
        return result;
    }

}
