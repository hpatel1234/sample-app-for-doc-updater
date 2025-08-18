package com.simple.webapp.dto;

import lombok.Builder;

@Builder
public class Filter {
    private String filterValue;
    private String filterOperation;
    private String filterColumn;
}
