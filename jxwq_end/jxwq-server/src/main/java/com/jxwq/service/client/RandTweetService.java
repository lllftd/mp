package com.jxwq.service.client;

import org.springframework.stereotype.Service;

import java.util.List;
import java.util.Map;

/**
 * @author: jxwq
 * @date: 2024/10/24 下午 09:51
 * @description:
 */
@Service
public interface RandTweetService {

    List<Map<String, Object>> recommendTweets(Integer clientUserId, String searchTypeKeyword);

}



