package com.simple.webapp.dto;

import lombok.Getter;
import lombok.Setter;

import java.util.List;

@Getter
@Setter
public class DerivativeTradeModel {
    private String lob;
    private String orgUnit;
    private String assetClass;
    private List<String> participants;
}

