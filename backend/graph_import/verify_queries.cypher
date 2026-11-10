// Entity and relationship counts
MATCH (entity:Entity)
RETURN count(entity) AS entity_count;

MATCH ()-[relationship:RELATED]->()
RETURN count(relationship) AS relationship_count;

// Distinct imported relation types
MATCH ()-[relationship:RELATED]->()
RETURN relationship.relation AS relation, count(*) AS occurrences
ORDER BY occurrences DESC;

// Sample graph
MATCH (subject:Entity)-[relationship:RELATED]->(object:Entity)
RETURN subject.name, relationship.relation, object.name, relationship.source_doc
LIMIT 25;
