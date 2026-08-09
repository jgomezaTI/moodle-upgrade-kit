SELECT classname,
       lastruntime,
       nextruntime,
       faildelay
FROM mdl_task_scheduled
WHERE faildelay > 0
ORDER BY faildelay DESC, classname;
