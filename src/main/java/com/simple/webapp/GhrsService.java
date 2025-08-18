package com.simple.webapp;

import com.simple.webapp.dto.DerivativeTradeDto;
import com.simple.webapp.dto.DerivativeTradeModel;
import com.simple.webapp.dto.Employee;
import com.simple.webapp.dto.Filter;

import java.util.ArrayList;
import java.util.List;

public class GhrsService {

    private GraphQLCLient graphQlClient;
    private String ghrsApi;

    public List<Employee> enrichEmployees(DerivativeTradeModel domain, DerivativeTradeDto dto) {
        List<Employee> employees = new ArrayList<>();
        for (String eid : dto.getEmployees()) {
            Filter f = Filter.builder().filterValue(eid).filterOperation("equals").filterColumn("employeeId").build();
            Employee e = graphQlClient.execute(ghrsApi, f);
            if (e != null) {
                employees.add(e);
            } else {
                throw new RuntimeException("Not found Employee id not found with id " + eid);
            }


        }
        return employees;
    }
}
