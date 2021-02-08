# Databricks notebook source
# MAGIC %md
# MAGIC ## Input parameters from the user
# MAGIC ** All Input parameters are mandatory . **
# MAGIC <br>The Cloud Trail Logs Path and Region Name can be obtained from AWS account admin.
# MAGIC 1. **Cloud Trail Logs Path** : The folder in the S3 bucket from which to collect data. It should be of the form `s3://<bucket-name>/AWSLogs/<aws-account-id>/CloudTrail/<bucket-region>/*`. Specify the specific AWS account id and bucket region in case there are multiple such directories in the S3 bucket or you may use \* in place for selecting all.
# MAGIC <br>**Example:** Cloud Trail Logs Path : `s3://mybucket/AWSLogs/1234567890/CloudTrail/us-east-1/*`
# MAGIC 2. **Delta Output Path** : The DBFS or S3 path where the parsed data files should be stored. Ensure that this path is either empty(contains no data files) or is not a pre-existing path or does not contain any data that does not follow Cloud Trail Logs schema (schema as specified in cmd 5).
# MAGIC <br>**Example:** Delta Output Path : `/cloudTrailLogData/`
# MAGIC 3. **Checkpoint Path** : The path for checkpoint files. The checkpoint files store information regarding the last processed record written to the table. Ensure that only one Cloud Trail Logs Path is associated with a given checkpoint Path, that is, the same checkpoint Path should not be used for any other Cloud Trail Logs Path.
# MAGIC <br>**Example:** Checkpoint Path : `/cloudTrailLogData.checkpoint`
# MAGIC 4. **Table Name** : The table name to create. A table name can contain only lowercase alphanumeric characters and underscores and must start with a lowercase letter or underscore. Ensure a table with provided name does not pre-exist, else it will not be created.
# MAGIC 5. **Region Name** : The region name in which the S3 bucket and the AWS SNS and SQS services are created.
# MAGIC <br>**Example:** Region Name : `us-east-1`
# MAGIC 
# MAGIC ##Troubleshooting
# MAGIC ###Issue
# MAGIC <p> cmd 12 throws "AnalysisException : You are trying to create an external table default.`<table>` from `<Delta Output Path>` using Databricks Delta, but the schema is not specified when the input path is empty". After a few seconds, the write stream command in cmd 9 will also stop with "stream stopped" message. This issue occurs when the write stream command in cmd 9 has not written output to `Delta Output Path>` and not completed initialization (indicated by "stream initializing" message displayed)</p>
# MAGIC 
# MAGIC ###Solution
# MAGIC <p>In case of above issue run the cmd 9 cell individually  using the `Run > Run cell` option on the top right corner of the cell. Once the stream initialization is completed, and some output is written to the `Delta Output Path>`, run the command in cmd 12 cell individually  using the `Run > Run cell` option on the top right corner of the cell.</p>

# COMMAND ----------

# Defining the user input widgets
dbutils.widgets.removeAll()
dbutils.widgets.text("Cloud Trail Logs Path","","1.Cloud Trail Logs Path")
dbutils.widgets.text("Delta Output Path","","2.Delta Output Path")
dbutils.widgets.text("Checkpoint Path","","3.Checkpoint Path")
dbutils.widgets.text("Table Name","","4.Table Name")
dbutils.widgets.text("Region Name","","5.Region Name")

# COMMAND ----------

# Reading the values of user input
cloudTrailLogsPath=dbutils.widgets.get("Cloud Trail Logs Path")
deltaOutputPath=dbutils.widgets.get("Delta Output Path")
checkpointPath=dbutils.widgets.get("Checkpoint Path")
tableName=dbutils.widgets.get("Table Name")
regionName=dbutils.widgets.get("Region Name")
if ((cloudTrailLogsPath==None or cloudTrailLogsPath=="")or(deltaOutputPath==None or deltaOutputPath=="")or(checkpointPath==None or checkpointPath=="")or(tableName==None or tableName=="")or(regionName==None or regionName=="")):
  dbutils.notebook.exit("All parameters are mandatory. Ensure correct values of all parameters are specified.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Defining schema for Cloud Trail Log events 
# MAGIC Reference : [CloudTrail Record Contents](https://docs.aws.amazon.com/awscloudtrail/latest/userguide/cloudtrail-event-reference-record-contents.html)

# COMMAND ----------

from pyspark.sql.functions import *
from pyspark.sql.types import *
from datetime import datetime
cloudTrailSchema = StructType() \
    .add("Records", ArrayType(StructType() \
        .add("eventTime", StringType()) \
        .add("eventVersion", StringType()) \
        .add("userIdentity", StructType() \
            .add("type", StringType()) \
            .add("userName", StringType()) \
            .add("principalId", StringType()) \
            .add("arn", StringType()) \
            .add("accountId", StringType()) \
            .add("accessKeyId", StringType()) \
            .add("invokedBy", StringType()) \
            .add("identityProvider", StringType()) \
            .add("sessionContext", StructType() \
                .add("attributes", StructType() \
                .add("creationDate", StringType()) \
                .add("mfaAuthenticated", StringType()) \
                ) \
             ) \
            .add("sessionIssuer", StructType() \
                .add("accountId", StringType()) \
                .add("arn", StringType()) \
                .add("principalId", StringType()) \
                .add("type", StringType()) \
                .add("userName", StringType()) \
            ) \
            .add("webIdFederationData", StructType() \
                .add("federatedProvider", StringType()) \
                .add("attributes", MapType(StringType(), StringType())) \
            ) \
        ) \
        .add("eventSource", StringType()) \
        .add("eventName", StringType()) \
        .add("awsRegion", StringType()) \
        .add("sourceIPAddress", StringType()) \
        .add("userAgent", StringType()) \
        .add("errorCode", StringType()) \
        .add("errorMessage", StringType()) \
        .add("requestParameters", MapType(StringType(), StringType())) \
        .add("responseElements", MapType(StringType(), StringType())) \
        .add("additionalEventData", MapType(StringType(), StringType())) \
        .add("requestID", StringType()) \
        .add("eventID", StringType()) \
        .add("readOnly", BooleanType()) \
        .add("eventType", StringType()) \
        .add("apiVersion", StringType()) \
        .add("managementEvent", BooleanType()) \
        .add("recipientAccountId", StringType()) \
        .add("vpcEndpointId", StringType()) \
        .add("eventCategory", StringType()) \
        .add("serviceEventDetails", MapType(StringType(), StringType())) \
        .add("sharedEventID", StringType()) \
        .add("resources", ArrayType(MapType(StringType(), StringType()))) \
        .add("sessionCredentialFromConsole", StringType()) \
        .add("edgeDeviceDetails", StringType()) \
        .add("tlsDetails", StructType() \
            .add("tlsVersion", StringType()) \
            .add("cipherSuite", StringType()) \
            .add("clientProvidedHostHeader", StringType()) \
        ) \
        .add("addendum", StructType() \
            .add("reason", StringType()) \
            .add("updatedFields", StringType()) \
            .add("originalRequestID", StringType()) \
            .add("originalEventID", StringType()) \
            ) \
     )) 

# COMMAND ----------

# MAGIC %md
# MAGIC ## Reading from the stream , parsing it and writing to delta files 

# COMMAND ----------

rawRecords = spark.readStream.format("cloudFiles") \
  .option("cloudFiles.format", "json") \
  .option("cloudFiles.includeExistingFiles", "true") \
  .option("cloudFiles.useNotifications", "true") \
  .option("cloudFiles.region", regionName) \
  .option("cloudFiles.validateOptions", "true") \
  .schema(cloudTrailSchema) \
  .load(cloudTrailLogsPath)

# COMMAND ----------

cloudTrailEvents = rawRecords \
  .select(explode("Records").alias("record")) \
  .select(
    unix_timestamp("record.eventTime", "yyyy-MM-dd'T'HH:mm:ss'Z'").cast("timestamp").alias("timestamp"),
    "record.*")

# COMMAND ----------

streamingETLQuery = cloudTrailEvents \
  .withColumn("date", cloudTrailEvents.timestamp.cast("date")) \
  .writeStream \
  .format("delta") \
  .partitionBy("date") \
  .outputMode("append") \
  .option("checkpointLocation", checkpointPath) \
  .start(deltaOutputPath)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Creating table from the parsed data

# COMMAND ----------

# The sleep statement is added here to wait for 5 mins till the write stream command in cmd 9 is initialized and parsed data starts to be written into the specified  deltaOutputPath so that the table can be created using command in cmd-12
#However even after waiting for 5 mins, the write stream command in cmd 9 has not written output to <Delta Output Path> and not completed initialization (indicated by "stream initializing" message displayed), the command in cmd 12 throws  `AnalysisException : You are trying to create an external table default.<table> from <Delta Output Path> using Databricks Delta, but the schema is not specified when the input path is empty`.After a few seconds, the write stream command in cmd 9 will also stop with `stream stopped` message. 
#In case of the above issue run the cmd 9 cell individually using the `Run > Run cell` option on the top right corner of the cell. Once the stream initialization is completed, and some output is written to the <Delta Output Path> , run the command in cmd 12 cell individually using the `Run > Run cell` option on the top right corner of the cell.
import time
time.sleep(300)

# COMMAND ----------

create_table_query="CREATE TABLE IF NOT EXISTS "+tableName+" USING DELTA LOCATION '"+ deltaOutputPath +"'"
spark.sql(create_table_query)
