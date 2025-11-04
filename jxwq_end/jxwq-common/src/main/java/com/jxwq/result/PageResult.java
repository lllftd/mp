package com.jxwq.result;

import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.io.Serializable;
import java.util.List;

/**
 * 封装分页查询结果
 */
@Data
@NoArgsConstructor // 无参构造器 有了就可以实例化的时候不传参
public class PageResult<T> implements Serializable {

    private static final long serialVersionUID = 1L;

    private int page; // 当前页码

    private int pageSize; // 每页条数

    private long totalPage; // 总页数

    private long total; // 总记录数

    private List<T> rows; // 当前页数据集合

    // 页码 每页多少条 总页数 总记录数 当前页数据集合
    public PageResult(int page, int pageSize, long totalPage, long total, List<T> rows) {
        this.page = page;
        this.pageSize = pageSize;
        this.totalPage = totalPage;
        this.total = total;
        this.rows = rows;
    }

}
