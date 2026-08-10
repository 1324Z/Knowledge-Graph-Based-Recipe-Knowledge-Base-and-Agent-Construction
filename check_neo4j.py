from neo4j import GraphDatabase

driver = GraphDatabase.driver('bolt://localhost:7687', auth=('neo4j', 'all-in-rag'))
try:
    with driver.session() as session:
        result = session.run('MATCH (n) RETURN labels(n) AS type, count(n) AS count')
        print('=== Neo4j Node Stats ===')
        for r in result:
            print(f'  {r["type"]}: {r["count"]}')
        
        result2 = session.run('MATCH ()-[r]->() RETURN type(r) AS rel, count(r) AS count')
        print('=== Relationship Stats ===')
        for r in result2:
            print(f'  {r["rel"]}: {r["count"]}')
        
        result3 = session.run('MATCH (r:Recipe) RETURN r.name AS name LIMIT 10')
        print('=== First 10 Recipes ===')
        for r in result3:
            print(f'  - {r["name"]}')
        
        print('\nNeo4j is running and accessible!')
except Exception as e:
    print(f'Connection failed: {e}')
finally:
    driver.close()
