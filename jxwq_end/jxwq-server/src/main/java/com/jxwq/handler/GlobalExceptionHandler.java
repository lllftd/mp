package com.jxwq.handler;

import com.aliyun.oss.ServiceException;
import com.jxwq.constant.MessageConstant;
import com.jxwq.exception.BaseException;
import com.jxwq.result.AjaxResult;
import com.jxwq.utils.StringUtils;
import lombok.extern.slf4j.Slf4j;
import org.springframework.dao.DuplicateKeyException;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;
import org.springframework.web.servlet.NoHandlerFoundException;

import javax.servlet.http.HttpServletRequest;
import java.sql.SQLIntegrityConstraintViolationException;
import java.util.LinkedHashMap;
import java.util.Map;

/**
 * 全局异常处理器，处理项目中抛出的业务异常
 */
@RestControllerAdvice
@Slf4j
public class GlobalExceptionHandler {

    // https://blog.csdn.net/w1014074794/article/details/106038996

    /**
     * 捕获业务异常
     *
     * @param ex 业务异常
     * @return 错误信息
     */
    @ExceptionHandler
    public AjaxResult exceptionHandler(BaseException ex) {
        // log.error("异常信息：{}", ex.getMessage());
        return AjaxResult.error(ex.getMessage());
    }

    /**
     * 处理数据重复异常
     *
     * @param ex 数据重复异常
     * @return 返回具体的值
     */
    @ExceptionHandler
    public AjaxResult exceptionHandler(DuplicateKeyException ex) {
        String message = ex.getMessage();
        // System.err.println("约束违反错误信息：" + message);

        // 尝试解析异常消息以获取具体的值
        // 假设异常消息格式类似于："Duplicate entry '测试1' for key 'idx_dict_name'"
        String[] parts = new String[0];
        if (message != null) {
            parts = message.split("'");
        }

        if (parts.length > 1) {
            String violatedValue = parts[1]; // 这应该是 "测试1"
            // System.err.println("违反约束的值：" + violatedValue);
            return AjaxResult.error(violatedValue + " - 已存在！");
        }

        return AjaxResult.error("数据已存在！");
    }

    /**
     * 处理空指针的异常
     *
     * @param request 请求信息
     * @param ex      异常信息
     * @return 错误信息
     */
    @ExceptionHandler(value = NullPointerException.class)
    public AjaxResult exceptionHandler(HttpServletRequest request, NullPointerException ex) {
        log.error("发生空指针异常！原因是:", ex);
        return AjaxResult.error("请求的数据格式不符!");
    }

    // 处理用户名重复异常
    @ExceptionHandler
    public AjaxResult exceptionHandler(SQLIntegrityConstraintViolationException ex) {
        // 这里是通过对报错信息的分析来判断的，一旦 Spring 框架修改了该报错信息的提示，则代码就失效了
        // 也可以使用其他的办法：例如再次查询数据库中是否有该用户，这样会造成服务器性能的浪费。
        String message = ex.getMessage();

        if (message.contains("Duplicate entry")) {
            String[] split = message.split(" ");
            String username = split[2];
            String msg = username + MessageConstant.ALREADY_EXISTS;
            return AjaxResult.error(msg);
        } else {
            return AjaxResult.error("未知错误");
        }
    }

    /**
     * 处理找不到请求的异常
     *
     * @param e 异常信息
     * @return 错误信息
     */
    @ExceptionHandler(NoHandlerFoundException.class)
    public ResponseEntity<Object> handleNoHandlerFoundException(NoHandlerFoundException e) {
        log.error("找不到请求，异常路径是：{}", e.getRequestURL());
        Map<String, Object> body = new LinkedHashMap<>();
        body.put("code", HttpStatus.NOT_FOUND.value());
        body.put("msg", "服务未找到");
        return new ResponseEntity<>(body, HttpStatus.NOT_FOUND);
    }

    /**
     * 处理参数校验异常
     *
     * @param ex 异常信息
     * @return 错误信息
     */
    @ExceptionHandler(MethodArgumentNotValidException.class)
    public AjaxResult handleValidationExceptions(MethodArgumentNotValidException ex) {
        StringBuilder stringBuilder = new StringBuilder();

        // 获取所有的验证不通过信息并拼接
        // ex.getBindingResult().getAllErrors().forEach(error -> {
        //     String fieldName = ((org.springframework.validation.FieldError) error).getField(); // 获取字段名称
        //     String errorMessage = error.getDefaultMessage();
        //     // username:账号格式为数字以及字母;password:密码不能为空;username:登录账号不能为空;
        //     stringBuilder.append(fieldName).append(":").append(errorMessage).append(";");
        // });
        // return AjaxResult.error(stringBuilder.toString());

        // 只提示第一个错误的信息
        String firstErrorMsg = ex.getBindingResult().getAllErrors().get(0).getDefaultMessage();
        return AjaxResult.error(firstErrorMsg);

    }

    /**
     * 业务异常
     */
    @ExceptionHandler(ServiceException.class)
    public AjaxResult handleServiceException(ServiceException e, HttpServletRequest request) {
        log.error(e.getMessage(), e);
        String code = e.getErrorCode();
        return StringUtils.isNotNull(code) ? AjaxResult.error(code, e.getMessage()) : AjaxResult.error(e.getMessage());
    }

    /**
     * 拦截未知的运行时异常
     */
    @ExceptionHandler(RuntimeException.class)
    public AjaxResult handleRuntimeException(RuntimeException e, HttpServletRequest request) {
        String requestURI = request.getRequestURI();
        // log.error("请求地址'{}',发生未知异常-RuntimeException", requestURI, e);
        log.error("请求地址'{}',发生未知异常-RuntimeException,异常原因'{}'", requestURI, e.getMessage());
        String msg = e.getMessage();
        if (!StringUtils.isBlank(msg)) {
            // 捕获这个异常信息，如果这个异常信息包含这个字符串就抛出自定义异常。
            if (msg.contains("Required request body is missing:")) {
                return AjaxResult.error("请求参数不能为空！");
            }
        }
        return AjaxResult.error(e.getMessage());
    }

    /**
     * 系统异常
     */
    @ExceptionHandler(Exception.class)
    public AjaxResult handleException(Exception e, HttpServletRequest request) {
        String requestURI = request.getRequestURI();
        log.error("请求地址'{}',发生系统异常-Exception", requestURI, e);
        return AjaxResult.error(e.getMessage());
    }

    // /**
    //  * 处理系统异常，兜底处理所有的一切
    //  */
    // @ExceptionHandler(value = Exception.class)
    // public Result<?> defaultExceptionHandler(Throwable ex) {
    //     // 返回 ERROR CommonResult
    //     return Result.error(INTERNAL_SERVER_ERROR.getReasonPhrase());
    // }
}
