select
    p.participant_id,
    p.tournament_id
from (
    values
    ('a', 't1'),
    ('b', 't1'),
    ('c', 't1'),
    ('d', 't1'),
    ('e', 't1'),
    ('x', 't2'),
    ('y', 't2')
) as p (participant_id, tournament_id)
