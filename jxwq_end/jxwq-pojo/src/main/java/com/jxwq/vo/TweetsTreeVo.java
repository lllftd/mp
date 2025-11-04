package com.jxwq.vo;

import lombok.Data;

import java.util.List;

/**
 * @author: jxwq
 * @date: 2024/09/14
 * @description:
 */
@Data
public class TweetsTreeVo {
    /**
     * 主键
     */
    private Integer id;
    /**
     * 类型名称
     */
    private String name;
    /**
     * 父类型id 一级节点为NULL
     */
    private Integer parentId;
    /**
     * 子类型集合
     */
    private List<TweetsTreeVo> children;
}
