package com.jxwq.config;

import com.baomidou.mybatisplus.core.handlers.MetaObjectHandler;
import com.jxwq.constant.AutoFillConstant;
import com.jxwq.context.BaseContext;
import com.jxwq.utils.CommonUtils;
import lombok.extern.slf4j.Slf4j;
import org.apache.ibatis.reflection.MetaObject;
import org.springframework.stereotype.Component;

import java.time.LocalDateTime;

/**
 * mybatis-plus 自动填充插件
 */
@Slf4j
@Component
public class MyMetaObjectHandler implements MetaObjectHandler {

    /**
     * 插入时的填充策略
     *
     * @param metaObject metaObject
     */
    @Override
    public void insertFill(MetaObject metaObject) {
        // 创建时间
        this.strictInsertFill(metaObject, AutoFillConstant.CREATE_TIME, LocalDateTime.class, LocalDateTime.now());
        // 更新时间
        this.strictInsertFill(metaObject, AutoFillConstant.UPDATE_TIME, LocalDateTime.class, LocalDateTime.now());
        // 存用户id会好一些 而不是用户名 TODO 区分客户端和后台
        if (BaseContext.getCurrentUserInfo() != null) {
            String id = CommonUtils.stringValue(BaseContext.getCurrentUserInfo().getId());
            // 创建用户
            this.strictInsertFill(metaObject, AutoFillConstant.CREATE_USER, String.class, id);
            // 更新用户
            this.strictInsertFill(metaObject, AutoFillConstant.UPDATE_USER, String.class, id);
        }

    }

    /**
     * 更新时的填充策略
     *
     * @param metaObject metaObject
     */
    @Override
    public void updateFill(MetaObject metaObject) {
        // 更新时间
        this.strictUpdateFill(metaObject, AutoFillConstant.UPDATE_TIME, LocalDateTime.class, LocalDateTime.now());
        if (BaseContext.getCurrentUserInfo() != null) {
            String id = CommonUtils.stringValue(BaseContext.getCurrentUserInfo().getId());
            // 更新用户
            this.strictInsertFill(metaObject, AutoFillConstant.UPDATE_USER, String.class, id);
        }
    }

}