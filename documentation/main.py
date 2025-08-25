import os
from mistralai import Mistral
from neomodel import config, db
from itertools import chain

# Neo4j config (set via env or directly)
config.DATABASE_URL = "bolt://neo4j:neo4j123@neo4j-instance:7687"
config.DATABASE_NAME ="neo4j"

#Mistrl API config
api_key = "5O9lFYNOhUwW6WPk6rqnuL2O7JEePBJ9"
model = "mistral-large-latest"

client = Mistral(api_key=api_key)

def list_final_attribute_names(className):
    query = f"""
    MATCH (class:Class) WHERE class.name='{className}'
    MATCH (class)-[:HAS_FIELD]-(fields:Field) RETURN fields.name as fieldNames
    """
    results,meta=db.cypher_query(query)
    final_attributes=[]
    for row in results:
        final_attributes.append(row[0])
    return final_attributes

def get_methods_dealing_with_attribute(className, attribute):
    at=attribute.lower()
    query = f"""
    MATCH (method:Method) WHERE method.code CONTAINS '{className}' 
    AND (lower(method.code) CONTAINS '.{at}' 
    OR lower(method.code) CONTAINS 'set{at}' 
    OR lower(method.code) CONTAINS 'get{at}') 
    RETURN DISTINCT method 
    """
    results,meta=db.cypher_query(query)
    methods_dealing_with_attributes=[]
    for row in results:
        methods_dealing_with_attributes.append(row[0])
    return methods_dealing_with_attributes

def get_context_for_attribute(className,finalAttributeName):
    print("Called "+finalAttributeName)
    methods_dealing_with_attributes = get_methods_dealing_with_attribute(className,finalAttributeName)
    all_methods_for_context = []
    for method in methods_dealing_with_attributes:
        callees_of_method = get_callees_of_method(method)
        callers_of_method = get_callers_of_method(method)
        combined = list(chain(callees_of_method, callers_of_method))
        unique = list({item.element_id: item for item in combined}.values())
        all_methods_for_context.extend(unique)
    return all_methods_for_context

# This will return list of all methods getting called by provided method
def get_callees_of_method(method):
    methodElementId = method.element_id
    query = f"""
    MATCH (m:Method) WHERE elementId(m)='{methodElementId}' 
    MATCH (m)-[:CALLS_METHOD]->(p:Method) RETURN p
    """
    rows,meta = db.cypher_query(query)
    callees_of_method=[]
    for m in rows:
        callees_of_method.append(m[0])
        indirect_calls = get_callees_of_method(m[0])
        callees_of_method.extend(indirect_calls)
    return callees_of_method

# This will return list of all methods which calls provided method
def get_callers_of_method(method):
    methodElementId = method.element_id
    query = f"""
    MATCH (m:Method) WHERE elementId(m)='{methodElementId}' 
    MATCH (p:Method)-[:CALLS_METHOD]->(m) RETURN p
    """
    rows,meta = db.cypher_query(query)
    callers_of_method=[]
    for m in rows:
        callers_of_method.append(m[0])
        indirect_calls = get_callers_of_method(m[0])
        callers_of_method.extend(indirect_calls)
    return callers_of_method

def create_doc(source):
    agent = client.beta.agents.create(
        model=model,
        name="WebSearch Agent",
        instructions="""
    You are a code interpreter and transformation logic documentation agent you need to perform below tasks:
    1. Read and analyse all code. 
    2. Prepare graph of nodes where nodes are class names and edges are method calls, maintaining all execution sequence
    3. Summarise each method implementation logic in natural language, in Transformation logic column.
    4. Produce html page describing all the transformation logic.
    Page MUST contain table with multiple columns. 
    Columns should be final output attribute name, raw input source attributes used in transformation, transformation logic, 
    static mappings if used any, should be mentioned as key value pair in json format always, any extra information you would like to provide.
    Include extra information in last column if you find any.
    Column names of tables Output Attribute, Input Attributes Used, Transformation Logic, Static Mappings Used, Extra information
    Output MUST only contain full html code, so that it is easy for user to copy what it needs.
    You need to create documentation for each output attribute separately, mentioning raw or intermediate attributes used in transformation, all steps performed in transformation including any intermediate and fallback transformation logic if any.
    Transformation logic should be summary of implementation without any references to class names.
    If logic is dependent on some kind of ordering of execution or function calls, keep them as is. If there are some intermediate transformations then always include those as well. 
    Please include intermediate transformation's input, intermediate transformation logic, intermediate output and in which final output attribute they are used in separate table.
    """,
        description="Agent able to read and analyze given code and create documentation out of it.",
        #tools = [{"type": "code_interpreter"}, {"type": "web_search"}]
    )

    result = client.beta.conversations.start(
        agent_id=agent.id,
        inputs= source
    )

    print("All result entries:")
    for entry in result.outputs:
        with open("documentation.html", "w") as file:
            file.write(entry.content)

if __name__ == "__main__":
    className = "DerivativeTradeModel"
    final_attribute_names = list_final_attribute_names(className)
    all_methods_for_context=[]
    for attribute in final_attribute_names:
        for m in get_context_for_attribute(className, attribute):
            all_methods_for_context.append(m)

    all_methods_for_context = list({item.element_id: item for item in all_methods_for_context}.values())
    print("Methods passed as context to agent are:")
    for m in all_methods_for_context:
        print(m._properties['name'])
    input=""
    for method in all_methods_for_context:
        input+=method._properties['code']
        input+=("\n")
    print(f'Source code passed as context is {input}')
    create_doc(input)
