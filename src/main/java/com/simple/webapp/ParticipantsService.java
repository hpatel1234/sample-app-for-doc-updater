package com.simple.webapp;

import com.simple.webapp.dto.DerivativeTradeModel;
import com.simple.webapp.dto.Employee;
import org.springframework.util.CollectionUtils;

import java.util.ArrayList;
import java.util.List;

public class ParticipantsService {
    public void enrichParticipants(DerivativeTradeModel domain, List<Employee> employees) {
        if (!CollectionUtils.isEmpty(employees)) {
            List<String> participants = new ArrayList<>();
            for (Employee e : employees) {
                participants.add(e.getFirstName() + " " + e.getLastName());
            }
            domain.setParticipants(participants);
        }

    }
}
