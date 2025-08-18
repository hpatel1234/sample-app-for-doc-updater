package com.simple.webapp;

import com.simple.webapp.dto.DerivativeTradeDto;
import com.simple.webapp.dto.DerivativeTradeModel;
import com.simple.webapp.dto.Employee;
import lombok.Getter;
import lombok.Setter;
import org.apache.commons.lang3.StringUtils;
import org.springframework.util.CollectionUtils;

import java.util.List;
import java.util.Map;

@Getter
@Setter
public class AlertOutputEntryTransformer {
    private static Map<String, String> getAssetMappings() {
        return Map.of("mss", "Markets Security", "rc", "Risk and compliance");
    }

    private GhrsService ghrsService;
    private ParticipantsService participantsService;

    public DerivativeTradeModel transform(DerivativeTradeDto dto) {

        DerivativeTradeModel domain = new DerivativeTradeModel();
        List<Employee> employees = getGhrsService().enrichEmployees(domain, dto);
        enrichExtraAttributes(dto, domain, employees);
        getParticipantsService().enrichParticipants(domain, employees);
        return domain;
    }

    private void enrichExtraAttributes(DerivativeTradeDto dto, DerivativeTradeModel domain, List<Employee> employees) {
        if (!CollectionUtils.isEmpty(employees)) {
            Employee e = employees.get(0);
            domain.setLob(e.getLineOfBusiness());
            domain.setOrgUnit(e.getCountry());
            domain.setAssetClass(enrichAssetClass(e.getRptL3Descr(), e.getRptL4Descr(), e.getRptL5Descr()));
        }

    }

    private String enrichAssetClass(String l3, String l4, String l5) {
        String assetClass = "TREASURE";
        if (StringUtils.isNotBlank(l5)) {
            assetClass = getAssetMappings().get(l5);
        } else if (StringUtils.isNotBlank(l4)) {
            assetClass = getAssetMappings().get(l4);
        } else if (StringUtils.isNotBlank(l3)) {
            assetClass = getAssetMappings().get(l3);
        }
        return assetClass;
    }
}
